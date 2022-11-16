from __future__ import annotations

import io
import json
import logging
import random
import re
from abc import ABC
from datetime import timezone
from functools import lru_cache
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

import aiohttp
import discord
import valorantx
from async_lru import alru_cache
from colorthief import ColorThief

# discord
from discord import Interaction, app_commands, ui, utils
from discord.app_commands import Choice, locale_str as _T
from discord.app_commands.checks import dynamic_cooldown
from discord.ext import commands

# valorantx
from valorantx import (
    Buddy,
    BuddyLevel,
    CurrencyID,
    MissionType,
    PatchNotes,
    PlayerCard,
    QueueID,
    RiotMultifactorError,
    Skin,
    Spray,
    SprayLevel,
)

# utils
from utils.chat_formatting import bold, italics, strikethrough
from utils.checks import cooldown_5s
from utils.emojis import LatteEmoji as Emoji
from utils.errors import CommandError
from utils.formats import format_relative
from utils.views import BaseView

# local
from ._client import Client as ValorantClient, RiotAuth
from ._database import Database, ValorantUser
from ._embeds import Embed
from ._enums import Point as PointEmoji, ValorantLocale as VLocale
from ._errors import NoAccountsLinked
from ._views import (
    CollectionView,
    FeaturedBundleView,
    MatchHistoryView,
    RiotMultiFactorModal,
    StatsView,
    SwitchAccountView,
)

# cogs
from .admin import Admin
from .context_menu import ContextMenu
from .errors import ErrorHandler
from .events import Events
from .notify import Notify

if TYPE_CHECKING:
    from discord import Client
    from valorantx import Agent, Bundle, PlayerTitle, SkinChroma, SkinLevel, Weapon

    from bot import LatteBot

    ClientBot = Union[Client, LatteBot]

_log = logging.getLogger(__name__)

MISSING = utils.MISSING

RIOT_ID_REGEX = r'(^.{1,16})+[#]+(.{1,5})$'
RIOT_ID_BAD_REGEX = r'[|^&+\-%*/=!>()<>?;:\\\'"\[\]{}_,]'


# - main cog


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """
    This allows the metaclass used for proper type detection to
    coexist with discord.py's metaclass
    """

    pass


class Valorant(Admin, Notify, Events, ContextMenu, ErrorHandler, commands.Cog, metaclass=CompositeMetaClass):
    """Valorant API Commands"""

    def __init__(self, bot: LatteBot) -> None:
        super().__init__()
        self.bot = bot

        # users
        self.valorant_users: Dict[int, ValorantUser] = {}

        # database
        self.db: Database = Database(bot)

        # colors thief
        self.colors: Dict[str, List[Tuple[int, int, int]]] = {}

        # context menu
        # self.ctx_user_store = app_commands.ContextMenu(
        #     name=_T('store'),
        #     callback=self.store_user_context,
        # )
        # self.ctx_user_nightmarket = app_commands.ContextMenu(
        #     name=_T('nightmarket'),
        #     callback=self.nightmarket_user_context,
        # )
        # self.ctx_user_point = app_commands.ContextMenu(
        #     name=_T('point'),
        #     callback=self.point_user_context,
        # )

        # self.ctx_user_party_request = app_commands.ContextMenu(
        #     name=_T('Party: Request to join'),
        #     callback=self.party_request_user_context,
        # )
        # self.ctx_user_party_invite = app_commands.ContextMenu(
        #     name=_T('party_invite'),
        #     callback=self.party_invite_user_context,
        # )
        # self.ctx_user_party_join = app_commands.ContextMenu(
        #     name=_T('party_join'),
        #     callback=self.party_join_user_context,
        # )
        # self.ctx_user_party_leave = app_commands.ContextMenu(
        #     name=_T('party_leave'),
        #     callback=self.party_leave_user_context
        # )
        # self.ctx_user_party_kick = app_commands.ContextMenu(
        #     name=_T('party_kick'),
        #     callback=self.party_kick_user_context
        # )

        # add context menus to bot
        # self.bot.tree.add_command(self.ctx_user_store)
        # self.bot.tree.add_command(self.ctx_user_nightmarket)
        # self.bot.tree.add_command(self.ctx_user_point)

    @property
    def display_emoji(self) -> discord.Emoji:
        return self.bot.get_emoji(998169266044022875)

    async def cog_load(self):

        await self.fetch_all_valorant_users()

        if self.v_client is MISSING:

            self.v_client = ValorantClient()
            await self.v_client.__aenter__()

            if self.v_client.http.riot_auth is valorantx.utils.MISSING:

                riot_auth = RiotAuth(self.bot.owner_id, self.bot.support_guild_id, self.bot)

                await riot_auth.authorize(username=self.bot.riot_username, password=self.bot.riot_password)

                client = await self.v_client.set_authorize(riot_auth)

                try:
                    await client.fetch_assets(force=False, reload=True)
                except Exception as e:
                    await client.fetch_assets(force=True, reload=True)
                    _log.error(f'Failed to fetch assets: {e}')
                finally:
                    _log.info('Valorant client loaded.')

                if client.is_ready():
                    content = await self.v_client.fetch_content()
                    for season in content.get_seasons():
                        if season.is_active():
                            self.v_client.season = self.v_client.get_season(uuid=season.id)
                            break

        # start tasks
        self.notify_alert.start()
        self.auto_logout.start()
        self.client_version.start()
        self.featured_bundle_cache.start()
        self.reset_cache.start()

        _log.info('Valorant client loaded.')

    async def cog_unload(self) -> None:

        # close all tasks
        self.notify_alert.stop()
        self.auto_logout.stop()
        self.client_version.stop()
        self.featured_bundle_cache.stop()
        self.reset_cache.stop()

        # remove context menus from bot
        # self.bot.tree.remove_command(self.ctx_user_store.name, type=self.ctx_user_store.type)
        # self.bot.tree.remove_command(self.ctx_user_nightmarket.name, type=self.ctx_user_nightmarket.type)
        # self.bot.tree.remove_command(self.ctx_user_point.name, type=self.ctx_user_point.type)
        # self.bot.tree.remove_command(self.ctx_user_party_request.name, type=self.ctx_user_party_request.type)
        # self.bot.tree.remove_command(self.ctx_user_party_invite.name, type=self.ctx_user_party_invite.type)
        # self.bot.tree.remove_command(self.ctx_user_party_join.name, type=self.ctx_user_party_join.type)
        # self.bot.tree.remove_command(self.ctx_user_party_leave.name, type=self.ctx_user_party_leave.type)
        # self.bot.tree.remove_command(self.ctx_user_party_kick.name, type=self.ctx_user_party_kick.type)

        # close valorant client
        self.v_client.clear()
        await self.v_client.close()
        self.valorant_users.clear()
        self.v_client = MISSING

        _log.info('Valorant client unloaded.')

    # useful functions

    # database

    async def fetch_all_valorant_users(self) -> None:
        async with self.bot.pool.acquire(timeout=150.0) as conn:
            accounts = await self.db.select_users(conn=conn)
            self.valorant_users = {account.id: account for account in accounts}
            #  if account.id not in self.bot.blacklist # TODO: add blacklist

    # - useful cache functions

    @alru_cache(maxsize=2048)
    async def fetch_user(self, *, id: int) -> ValorantUser:

        v_user = self._get_user(id)
        if v_user is not None:
            return v_user

        v_user = await self.db.select_user(id)

        if v_user is None:
            self.fetch_user.invalidate(self, id=id)
            raise NoAccountsLinked('You have no accounts linked.')

        self.valorant_users[id] = v_user

        return v_user

    @lru_cache(maxsize=1)
    def get_all_agents(self) -> List[Agent]:
        return list(self.v_client.get_all_agents())

    @lru_cache(maxsize=1)
    def get_all_bundles(self) -> List[Bundle]:
        return list(self.v_client.get_all_bundles())

    @lru_cache(maxsize=1)
    def get_all_buddies(self) -> List[Buddy]:
        return list(self.v_client.get_all_buddies())

    @lru_cache(maxsize=1)
    def get_all_buddy_levels(self) -> List[BuddyLevel]:
        return list(self.v_client.get_all_buddy_levels())

    @lru_cache(maxsize=1)
    def get_all_player_cards(self) -> List[PlayerCard]:
        return list(self.v_client.get_all_player_cards())

    @lru_cache(maxsize=1)
    def get_all_player_titles(self) -> List[PlayerTitle]:
        return list(self.v_client.get_all_player_titles())

    @lru_cache(maxsize=1)
    def get_all_sprays(self) -> List[Spray]:
        return list(self.v_client.get_all_sprays())

    @lru_cache(maxsize=1)
    def get_all_spray_levels(self) -> List[SprayLevel]:
        return list(self.v_client.get_all_spray_levels())

    @lru_cache(maxsize=1)
    def get_all_skins(self) -> List[Skin]:
        return list(self.v_client.get_all_skins())

    @lru_cache(maxsize=1)
    def get_all_skin_levels(self) -> List[SkinLevel]:
        return list(self.v_client.get_all_skin_levels())

    @lru_cache(maxsize=1)
    def get_all_skin_chromas(self) -> List[SkinChroma]:
        return list(self.v_client.get_all_skin_chromas())

    @lru_cache(maxsize=1)
    def get_all_weapons(self) -> List[Weapon]:
        return list(self.v_client.get_all_weapons())

    @alru_cache(maxsize=30)
    async def get_patch_notes(self, locale: discord.Locale) -> PatchNotes:
        return await self.v_client.fetch_patch_notes(str(self.v_locale(locale)))

    @alru_cache(maxsize=1)
    async def get_featured_bundle(self) -> List[valorantx.FeaturedBundle]:
        try:
            v_user = await self.fetch_user(id=self.bot.owner_id)  # super user
        except NoAccountsLinked:
            riot_acc = RiotAuth(self.bot.owner_id, self.bot.support_guild_id, bot=self.bot)
            await riot_acc.authorize(username=self.bot.riot_username, password=self.bot.riot_password)
        else:
            riot_acc = v_user.get_1st()
        client = await self.v_client.set_authorize(riot_acc)
        data = await client.fetch_store_front()
        return data.get_bundles()

    @staticmethod
    def v_locale(locale: discord.Locale) -> VLocale:
        return VLocale.from_discord(str(locale))

    def get_color(self, id: str) -> List[Tuple[int, int, int]]:
        return self.colors.get(id)

    def set_color(self, id: str, color: List[Tuple[int, int, int]]) -> None:
        self.colors[id] = color

    async def fetch_color(
        self,
        id: str,
        image: Union[valorantx.Asset, str],
        palette: int = 0,
    ) -> List[Tuple[int]]:

        color = self.get_color(id)
        if color is None:

            if isinstance(image, valorantx.Asset):
                _file = await image.to_file(filename=id)
                to_bytes = _file.fp
            else:
                to_bytes = io.BytesIO(await self.v_client.http.read_from_url(image))

            if palette > 0:
                color = ColorThief(to_bytes).get_palette(color_count=palette)
            else:
                color = [ColorThief(to_bytes).get_color()]

            self.set_color(id, color)

        return color

    def _get_user(self, _id: int) -> Optional[ValorantUser]:
        return self.valorant_users.get(_id)

    def _pop_user(self, _id: int) -> Optional[ValorantUser]:
        return self.valorant_users.pop(_id, None)

    def set_valorant_user(
        self, user_id: int, guild_id: int, locale: discord.Locale, riot_auth: RiotAuth
    ) -> ValorantUser:
        self.valorant_users[user_id] = v_user = ValorantUser.from_login(riot_auth, user_id, guild_id, locale, self.bot)
        return v_user

    def add_riot_auth(self, user_id: int, riot_auth: RiotAuth) -> ValorantUser:
        v_user = self._get_user(user_id)
        v_user.add_account(riot_auth)
        return v_user

    def cache_clear(self):
        self.fetch_user.cache_clear()
        self.get_all_agents.cache_clear()
        self.get_all_bundles.cache_clear()
        self.get_all_buddies.cache_clear()
        self.get_all_buddy_levels.cache_clear()
        self.get_all_player_cards.cache_clear()
        self.get_all_player_titles.cache_clear()
        self.get_all_sprays.cache_clear()
        self.get_all_spray_levels.cache_clear()
        self.get_all_skins.cache_clear()
        self.get_all_skin_levels.cache_clear()
        self.get_all_skin_chromas.cache_clear()
        self.get_all_weapons.cache_clear()
        self.get_patch_notes.cache_clear()
        self.get_featured_bundle.cache_clear()

    def cache_invalidate(self, riot_auth: RiotAuth):

        for locale in VLocale:
            self.get_store.invalidate(self, riot_auth, locale)
            self.get_battlepass.invalidate(self, riot_auth, locale)
            self.get_nightmarket.invalidate(self, riot_auth, locale)
            self.get_point.invalidate(self, riot_auth, locale)
            self.get_mission.invalidate(self, riot_auth, locale)

    async def invite_by_display_name(self, party: valorantx.Party, display_name: str) -> None:

        if re.findall(RIOT_ID_BAD_REGEX, display_name) or not re.findall(RIOT_ID_REGEX, display_name):
            raise CommandError('Invalid Riot ID.')

        await party.invite_by_display_name(display_name=display_name)

    # functions

    @alru_cache(maxsize=1024)
    async def get_store(self, riot_auth: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US) -> List[discord.Embed]:

        client = await self.v_client.set_authorize(riot_auth)
        data = await client.fetch_store_front()
        store = data.get_store()

        embeds = [
            Embed(
                description=f"Daily store for {bold(client.user.display_name)}\n"
                f"Resets {format_relative(store.reset_at)}"
            )
        ]

        for skin in store.get_skins():
            e = Embed(
                title=f"{skin.rarity.emoji} {bold(skin.name_localizations.from_locale(str(locale)))}",  # type: ignore
                description=f"{PointEmoji.valorant_point} {skin.price}",
                colour=self.bot.theme.dark,
            )
            if skin.display_icon is not None:
                e.url = skin.display_icon.url
                e.set_thumbnail(url=skin.display_icon)

            if skin.rarity is not None:
                e.colour = int(skin.rarity.highlight_color[0:6], 16)

            embeds.append(e)

        return embeds

    @alru_cache(maxsize=1024)
    async def get_battlepass(
        self, riot_auth: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US
    ) -> List[discord.Embed]:

        client = await self.v_client.set_authorize(riot_auth)
        contract = await client.fetch_contracts()

        btp = contract.get_latest_contract(relation_type=valorantx.RelationType.season)

        next_reward = btp.get_next_reward()

        embed = discord.Embed(
            title=f"Battlepass for {bold(client.user.display_name)}",
            description=f"{bold('NEXT')}: {next_reward.display_name}",
        )
        embed.set_footer(text=f'TIER {btp.current_tier} | {btp.name_localizations.from_locale(str(locale))}')

        if next_reward is not None:
            if next_reward.display_icon is not None:
                if isinstance(next_reward, valorantx.SkinLevel):
                    embed.set_image(url=next_reward.display_icon)
                elif isinstance(next_reward, valorantx.PlayerCard):
                    embed.set_image(url=next_reward.wide_icon)
                else:
                    embed.set_thumbnail(url=next_reward.display_icon)

        embed.colour = self.bot.theme.purple if btp.current_tier <= 50 else self.bot.theme.gold

        return [embed]

    @alru_cache(maxsize=1024)
    async def get_nightmarket(
        self, riot_auth: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US
    ) -> List[discord.Embed]:

        client = await self.v_client.set_authorize(riot_auth)
        data = await client.fetch_store_front()

        nightmarket = data.get_nightmarket()

        if nightmarket is None:
            raise CommandError(f"{bold('Nightmarket')} is not available.")

        embeds = [
            Embed(
                description=f"NightMarket for {bold(client.user.display_name)}\n"
                f"Expires {format_relative(nightmarket.expire_at)}",
                colour=self.bot.theme.purple,
            )
        ]

        for skin in nightmarket.get_skins():
            e = Embed(
                title=f"{skin.rarity.emoji} {bold(skin.name_localizations.from_locale(str(locale)))}",  # type: ignore
                description=f"{PointEmoji.valorant_point} {bold(str(skin.discount_price))}\n"
                f"{PointEmoji.valorant_point}  {strikethrough(str(skin.price))} (-{skin.discount_percent}%)",
                colour=self.bot.theme.dark,
            )
            if skin.display_icon is not None:
                e.url = skin.display_icon.url
                e.set_thumbnail(url=skin.display_icon)

            if skin.rarity is not None:
                e.colour = int(skin.rarity.highlight_color[0:6], 16)

            embeds.append(e)

        return embeds

    @alru_cache(maxsize=1024)
    async def get_point(self, riot_auth: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US) -> List[discord.Embed]:

        client = await self.v_client.set_authorize(riot_auth)
        wallet = await client.fetch_wallet()

        vp = client.get_currency(uuid=str(CurrencyID.valorant_point))
        rad = client.get_currency(uuid=str(CurrencyID.radianite_point))

        vp_display_name = vp.name_localizations.from_locale(str(locale))

        embed = Embed(title=f"{client.user.display_name} Point:")
        embed.add_field(
            name=f"{(vp_display_name if vp_display_name != 'VP' else 'Valorant Points')}",
            value=f"{vp.emoji} {wallet.valorant_points}",
        )
        embed.add_field(
            name=f'{rad.name_localizations.from_locale(str(locale))}',
            value=f'{rad.emoji} {wallet.radiant_points}',
        )

        return [embed]

    @alru_cache(maxsize=1024)
    async def get_mission(
        self, riot_auth: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US
    ) -> List[discord.Embed]:

        client = await self.v_client.set_authorize(riot_auth)
        contracts = await client.fetch_contracts()

        daily = []
        weekly = []
        tutorial = []
        npe = []

        all_completed = True

        daily_format = '{0} | **+ {1.xp:,} XP**\n- **`{1.progress}/{1.target}`**'
        for mission in contracts.missions:
            title = mission.title_localizations.from_locale(str(locale))
            if mission.type == MissionType.daily:
                daily.append(daily_format.format(title, mission))
            elif mission.type == MissionType.weekly:
                weekly.append(daily_format.format(title, mission))
            elif mission.type == MissionType.tutorial:
                tutorial.append(daily_format.format(title, mission))
            elif mission.type == MissionType.npe:
                npe.append(daily_format.format(title, mission))

            if not mission.is_completed():
                all_completed = False

        embed = Embed(title=f"{client.user.display_name} Mission:")
        if all_completed:
            embed.colour = 0x77DD77

        if len(daily) > 0:
            embed.add_field(
                name=f"**Daily**",
                value='\n'.join(daily),
                inline=False,
            )

        if len(weekly) > 0:

            weekly_refill_time = None
            if contracts.mission_metadata is not None:
                if contracts.mission_metadata.weekly_refill_time is not None:
                    weekly_refill_time = format_relative(contracts.mission_metadata.weekly_refill_time)

            embed.add_field(
                name=f"**Weekly**",
                value='\n'.join(weekly)
                + ('\n\n' + "Refill Time: " + weekly_refill_time if weekly_refill_time is not None else ''),
                inline=False,
            )

        if len(tutorial) > 0:
            embed.add_field(
                name=f"**Tutorial**",
                value='\n'.join(tutorial),
                inline=False,
            )

        if len(npe) > 0:
            embed.add_field(
                name=f"**NPE**",
                value='\n'.join(npe),
                inline=False,
            )

        return [embed]

    @alru_cache(maxsize=1024)
    async def get_collection(
        self, riot_auth: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US
    ) -> Tuple[List[discord.Embed], List[discord.Embed], List[List[discord.Embed]]]:

        client = await self.v_client.set_authorize(riot_auth)

        # mmr
        mmr = await client.fetch_mmr()
        latest_tier = mmr.get_last_rank_tier()

        # wallet
        wallet = await client.fetch_wallet()
        vp = client.get_currency(uuid=str(CurrencyID.valorant_point))
        rad = client.get_currency(uuid=str(CurrencyID.radianite_point))

        # loadout
        collection = await client.fetch_loadout()
        player_title = collection.get_player_title()
        player_card = collection.get_player_card()

        e = discord.Embed()
        e.description = f"{vp.emoji} {wallet.valorant_points}" + ' ' + f"{rad.emoji} {wallet.radiant_points}"
        e.set_author(
            name=f'{riot_auth.display_name} - Collection',
            icon_url=latest_tier.large_icon if latest_tier is not None else None,
        )

        if player_title is not None:
            e.title = player_title.text_localizations.from_locale(locale)

        if player_card is not None:
            e.set_image(url=player_card.wide_icon)
            card_color_thief = await self.fetch_color(player_card.uuid, player_card.wide_icon)
            e.colour = discord.Colour.from_rgb(*(random.choice(card_color_thief)))

        e.set_footer(text=f'Lv. {collection.identity.account_level}')

        async def _spray_page() -> List[discord.Embed]:
            embeds = []
            for spray in collection.get_sprays():
                spray_fav = ' ★' if spray.is_favorite() else ''
                embed = discord.Embed(description=bold(spray.display_name) + spray_fav)
                spray_icon = spray.animation_gif or spray.full_transparent_icon or spray.display_icon
                if spray_icon is not None:
                    embed.set_thumbnail(url=spray_icon)
                    spray_color_thief = await self.fetch_color(spray.uuid, spray.display_icon)
                    embed.colour = discord.Colour.from_rgb(*(random.choice(spray_color_thief)))
                embeds.append(embed)
            return embeds

        def _skin_page() -> List[List[discord.Embed]]:

            all_embeds = []
            embeds = []

            def sort_skins(
                skin_sort: Union[
                    valorantx.SkinLoadout,
                    valorantx.SkinLevelLoadout,
                    valorantx.SkinChromaLoadout,
                ]
            ) -> int:

                skin_ = skin_sort if isinstance(skin_sort, valorantx.SkinLoadout) else skin_sort.get_skin()

                weapon = skin_.get_weapon()

                # page 1
                if weapon.display_name == 'Phantom':
                    return 0
                elif weapon.display_name == 'Vandal':
                    return 1
                elif weapon.display_name == 'Operator':
                    return 2
                elif weapon.is_melee():
                    return 3

                # page 2
                elif weapon.display_name == 'Classic':
                    return 4
                elif weapon.display_name == 'Sheriff':
                    return 5
                elif weapon.display_name == 'Spectre':
                    return 6
                elif weapon.display_name == 'Marshal':
                    return 7

                # page 3
                elif weapon.display_name == 'Stinger':
                    return 8
                elif weapon.display_name == 'Bucky':
                    return 9
                elif weapon.display_name == 'Guardian':
                    return 10
                elif weapon.display_name == 'Ares':
                    return 11

                # page 4
                elif weapon.display_name == 'Shorty':
                    return 12
                elif weapon.display_name == 'Frenzy':
                    return 13
                elif weapon.display_name == 'Ghost':
                    return 14
                elif weapon.display_name == 'Judge':
                    return 15

                # page 5
                elif weapon.display_name == 'Bulldog':
                    return 16
                elif weapon.display_name == 'Odin':
                    return 17

            for index, skin in enumerate(sorted(collection.get_skins(), key=sort_skins)):

                skin_fav = ' ★' if skin.is_favorite() else ''

                embed = discord.Embed(
                    description=(skin.rarity.emoji if skin.rarity is not None else '')  # type: ignore
                    + ' '
                    + bold(
                        (
                            skin.display_name
                            if not isinstance(skin, valorantx.SkinChromaLoadout)
                            else skin.get_skin().display_name
                        )
                        + skin_fav
                    ),
                    colour=int(skin.rarity.highlight_color[0:6], 16)
                    if skin.rarity is not None
                    else self.bot.theme.dark,
                )
                embed.set_thumbnail(url=skin.display_icon)

                buddy = skin.get_buddy()
                if buddy is not None:
                    buddy_fav = ' ★' if buddy.is_favorite() else ''
                    embed.set_footer(
                        text=f'{buddy.display_name}' + buddy_fav,
                        icon_url=buddy.display_icon,
                    )

                embeds.append(embed)
                if len(embeds) == 4:
                    all_embeds.append(embeds)
                    embeds = []

            if len(embeds) != 0:
                all_embeds.append(embeds)

            return all_embeds

        return [e], await _spray_page(), _skin_page()

    # --

    @app_commands.command(name=_T('login'), description=_T('Log in with your Riot accounts'))
    @app_commands.describe(username=_T('Input username'), password=_T('Input password'))
    @app_commands.rename(username=_T('username'), password=_T('password'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def login(
        self,
        interaction: Interaction,
        username: app_commands.Range[str, 1, 24],
        password: app_commands.Range[str, 1, 128],
    ) -> None:

        v_user = self._get_user(interaction.user.id)
        if v_user is not None:
            if len(v_user.get_riot_accounts()) >= 5:
                raise CommandError('You can only have up to 5 accounts linked.')

        try_auth = RiotAuth(interaction.user.id, interaction.guild_id, self.bot)

        try:
            await try_auth.authorize(username, password, remember=True)
        except RiotMultifactorError:
            wait_modal = RiotMultiFactorModal(try_auth)
            await interaction.response.send_modal(wait_modal)
            await wait_modal.wait()

            # when timeout
            if wait_modal.code is None:
                raise CommandError('You did not enter the code in time.')

            await try_auth.authorize_multi_factor(wait_modal.code, remember=True)

            # replace interaction
            interaction = wait_modal.interaction
            await interaction.response.defer(ephemeral=True)
        except aiohttp.ClientResponseError:
            raise CommandError('Riot server is currently unavailable.')
        else:
            await interaction.response.defer(ephemeral=True)

        if v_user is None:
            try_auth.acc_num = 1
            v_user = self.set_valorant_user(interaction.user.id, interaction.guild_id, interaction.locale, try_auth)
        else:
            for auth_u in v_user.get_riot_accounts():
                if auth_u.puuid == try_auth.puuid:
                    raise CommandError('You already have this account linked.')
            self.add_riot_auth(interaction.user.id, try_auth)

        # insert to database sql and encrypt data

        payload = list(riot_auth.to_dict() for riot_auth in v_user.get_riot_accounts())

        # encryption
        encrypt_payload = self.bot.encryption.encrypt(json.dumps(payload))

        await self.db.upsert_user(
            encrypt_payload,
            interaction.user.id,
            interaction.guild_id,
            interaction.locale,
        )

        # invalidate cache
        self.fetch_user.invalidate(self, id=interaction.user.id)

        e = Embed(description=f"Successfully logged in {bold(try_auth.display_name)}")

        # TOS, privacy views
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name=_T('logout'), description=_T('Logout and Delete your accounts from database'))
    @app_commands.guild_only()
    @app_commands.rename(number=_T('account'))
    @dynamic_cooldown(cooldown_5s)
    async def logout(self, interaction: Interaction, number: Optional[str] = None) -> None:

        await interaction.response.defer(ephemeral=True)

        async with self.bot.pool.acquire(timeout=150.0) as conn:

            if number is None or number == '-':

                await self.db.delete_user(interaction.user.id, conn=conn)

                v_user = self._pop_user(interaction.user.id)
                if v_user is not None:
                    for acc in v_user.get_riot_accounts():
                        # validate cache
                        self.cache_invalidate(acc)

                e = Embed(description=f"Successfully logged out all accounts")
                await interaction.followup.send(embed=e, ephemeral=True)

            elif int(number) in range(1, 6):

                v_user = await self.fetch_user(id=interaction.user.id)
                if v_user is None:
                    v_user = await self.db.select_user(interaction.user.id, conn=conn)
                    if v_user is None:
                        raise CommandError('You have no accounts linked.')

                for auth_u in v_user.get_riot_accounts():
                    if auth_u.acc_num == int(number):
                        self.cache_invalidate(auth_u)
                        break

                # remove from database
                riot_auth_remove = v_user.remove_account(int(number))

                if len(v_user.get_riot_accounts()) == 0:
                    await self.db.delete_user(interaction.user.id, conn=conn)
                    self._pop_user(interaction.user.id)
                else:
                    await self.db.upsert_user(
                        v_user.data_encrypted(),
                        v_user.id,
                        v_user.guild_id,
                        interaction.locale,
                        v_user.date_signed,
                        conn=conn,
                    )

                e = Embed(description=f"Successfully logged out {bold(riot_auth_remove.display_name)}")

                await interaction.followup.send(embed=e, ephemeral=True)

            else:
                raise CommandError('Invalid number.')

        # invalidate cache
        self.fetch_user.invalidate(self, id=interaction.user.id)

    @logout.autocomplete('number')
    async def logout_autocomplete(self, interaction: Interaction, current: str) -> List[Choice[str]]:

        get_user = self._get_user(interaction.user.id)
        if get_user is None:
            return [
                Choice(name="You have no accounts linked.", value="-"),
            ]

        return [
            Choice(name=f"{user.acc_num}. {user.display_name} ", value=str(user.acc_num))
            for user in sorted(get_user.get_riot_accounts(), key=lambda x: x.acc_num)
        ]

    @app_commands.command(name=_T('store'), description=_T('Shows your daily store in your accounts'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def store(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)

        embeds = await self.get_store(v_user.get_1st(), self.v_locale(interaction.locale))

        switch_view = SwitchAccountView(interaction, v_user.get_riot_accounts(), self.get_store)
        await interaction.followup.send(embeds=embeds, view=switch_view)

    @app_commands.command(name=_T('nightmarket'), description=_T('Show skin offers on the nightmarket'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.guild_only()
    async def nightmarket(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)

        embeds = await self.get_nightmarket(v_user.get_1st(), self.v_locale(interaction.locale))

        switch_view = SwitchAccountView(interaction, v_user.get_riot_accounts(), self.get_nightmarket)
        await interaction.followup.send(embeds=embeds, view=switch_view)

    @app_commands.command(name=_T('battlepass'), description=_T('View your battlepass current tier'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def battlepass(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)

        embeds = await self.get_battlepass(v_user.get_1st(), self.v_locale(interaction.locale))
        switch_view = SwitchAccountView(interaction, v_user.get_riot_accounts(), self.get_battlepass)

        await interaction.followup.send(embeds=embeds, view=switch_view)

    @app_commands.command(name=_T('point'), description=_T('View your remaining Valorant and Riot Points (VP/RP)'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.guild_only()
    async def point(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)

        switch_view = SwitchAccountView(interaction, v_user.get_riot_accounts(), self.get_point)
        embeds = await self.get_point(v_user.get_1st(), self.v_locale(interaction.locale))

        await interaction.followup.send(embeds=embeds, view=switch_view)

    @app_commands.command(name=_T('bundles'), description=_T('Show the current featured bundles'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.guild_only()
    async def bundles(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        locale = self.v_locale(interaction.locale)

        bundles = await self.get_featured_bundle()

        select_view = FeaturedBundleView(interaction, bundles)

        all_embeds: Dict[str, List[discord.Embed]] = {}

        embeds_stuffs = []

        for bundle in bundles:

            # build embeds stuff
            s_embed = discord.Embed(title=bundle.name_localizations.from_locale(str(locale)), description='')
            if bundle.description_extra is not None:
                s_embed.description += f'{italics(bundle.description_extra_localizations.from_locale(str(locale)))}\n'
            s_embed.description += (
                f'{PointEmoji.valorant_point} {bold(str(bundle.discount_price))} - '
                f'expires {format_relative(bundle.expires_at)}'
            )

            if bundle.display_icon_2 is not None:
                s_embed.set_thumbnail(url=bundle.display_icon_2)
                color_thief = await self.fetch_color(bundle.uuid, bundle.display_icon_2)
                s_embed.colour = discord.Colour.from_rgb(*(random.choice(color_thief)))

            embeds_stuffs.append(s_embed)

            # build embeds
            embeds = []
            embed = Embed(
                description=f"Featured Bundle: {bold(f'{bundle.name_localizations.from_locale(str(locale))} Collection')}\n"  # noqa: E501
                f"{PointEmoji.valorant_point} {bold(str(bundle.discount_price))} {strikethrough(str(bundle.price))} "
                f"{italics(f'(Expires {format_relative(bundle.expires_at)})')}",
                colour=self.bot.theme.purple,
            )
            if bundle.display_icon_2 is not None:
                embed.set_image(url=bundle.display_icon_2)

            embeds.append(embed)

            for item in sorted(bundle.items, key=lambda i: i.price, reverse=True):
                emoji = item.rarity.emoji if isinstance(item, Skin) else ''  # type: ignore

                price_label = f"{PointEmoji.valorant_point} "

                item_price = item.price
                item_discounted_price = item.discounted_price

                if not isinstance(item, valorantx.SkinBundle) or item.is_melee():
                    price_label += f"{bold('FREE')} {strikethrough(str(item_price))}"
                else:
                    if item_discounted_price != item_price and item_discounted_price != 0:
                        price_label += f"{bold(str(item_discounted_price))} {strikethrough(str(item_price))}"
                    else:
                        price_label += f"{item_price}"

                e = Embed(
                    title=f"{emoji} {bold(item.display_name)}",
                    description=price_label,
                    colour=self.bot.theme.dark,
                )
                if isinstance(item, PlayerCard):
                    item_icon = item.large_icon
                elif isinstance(item, Spray):
                    item_icon = item.animation_gif or item.full_transparent_icon or item.full_icon or item.display_icon
                else:
                    item_icon = item.display_icon

                if item_icon is not None:
                    e.url = item_icon.url
                    e.set_thumbnail(url=item_icon)
                embeds.append(e)

            all_embeds[bundle.uuid] = embeds

        select_view.all_embeds = all_embeds

        if len(all_embeds) > 1:
            await interaction.followup.send(embeds=embeds_stuffs, view=select_view)
        elif len(all_embeds) == 1:
            await interaction.followup.send(embeds=all_embeds[list(all_embeds.keys())[0]])
        else:
            await interaction.followup.send("No featured bundles found")

    @app_commands.command(name=_T('mission'), description=_T('View your daily/weekly mission progress'))
    @dynamic_cooldown(cooldown_5s)
    async def mission(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)

        embeds = await self.get_mission(v_user.get_1st(), self.v_locale(interaction.locale))
        switch_view = SwitchAccountView(interaction, v_user.get_riot_accounts(), self.get_mission)

        await interaction.followup.send(embeds=embeds, view=switch_view)

    @app_commands.command(name=_T('collection'), description=_T('Shows your collection'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.guild_only()
    async def collection(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)

        embeds, sprays, skins = await self.get_collection(v_user.get_1st(), self.v_locale(interaction.locale))

        switch_view = CollectionView(
            interaction,
            v_user.get_riot_accounts(),
            self.get_collection,
            spray_pages=sprays,
            skin_pages=skins,
        )

        await interaction.followup.send(embeds=embeds, view=switch_view)
        switch_view.current_embeds = embeds

    @app_commands.command(name=_T('match'), description=_T('Last match history'))
    @app_commands.choices(
        queue=[
            Choice(name=_T('Unrated'), value='unrated'),
            Choice(name=_T('Competitive'), value='competitive'),
            Choice(name=_T('Deathmatch'), value='deathmatch'),
            Choice(name=_T('Spike Rush'), value='spikerush'),
            Choice(name=_T('Escalation'), value='escalation'),
            Choice(name=_T('Replication'), value='replication'),
            Choice(name=_T('Snowball Fight'), value='snowball'),
            Choice(name=_T('Custom'), value='custom'),
        ]
    )
    @app_commands.describe(queue=_T('Choose the queue'))
    @app_commands.rename(queue=_T('queue'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.guild_only()
    async def match(self, interaction: Interaction, queue: Choice[str] = "null") -> None:
        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)
        client = await self.v_client.set_authorize(v_user.get_1st())
        match_history = await client.fetch_match_history(queue=QueueID.competitive)

        if len(match_history) <= 0:
            # raise NoMatchHistory('No match history found')
            raise CommandError('No match history found')

        view = MatchHistoryView(interaction, match_history.get_match_details())
        await view.start()

    @app_commands.command(name=_T('patchnote'), description=_T('Patch notes'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.guild_only()
    async def patchnote(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        patch_notes = await self.get_patch_notes(interaction.locale)

        latest = patch_notes.get_latest_patch_note()

        embed = discord.Embed(
            title=latest.title,
            timestamp=latest.timestamp.replace(tzinfo=timezone.utc),
            url=latest.url,
            description=italics(latest.description),
        )

        # banner
        scraper = await self.v_client.scraper_patch_note(latest.url)
        banner_url = scraper.banner or latest.banner
        if banner_url is not None:
            embed.set_image(url=banner_url)
            color_thief = await self.fetch_color(latest.uid, banner_url, 5)
            embed.colour = discord.Colour.from_rgb(*(random.choice(color_thief)))

        view = discord.ui.View()  # TODO: URLButton class
        view.add_item(
            discord.ui.Button(
                label=patch_notes.see_article_title,
                url=latest.url,
                emoji=Emoji.link_standard,
            )
        )

        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name=_T('agent'), description=_T('View agent info'))
    @app_commands.guild_only()
    @app_commands.rename(agent='agent')
    @dynamic_cooldown(cooldown_5s)
    async def agent(self, interaction: Interaction, agent: str = None) -> None:

        # หน้าเลือก agent role n.nextcord

        await interaction.response.defer()

        locale = self.v_locale(interaction.locale)

        get_agent = self.v_client.get_agent(agent)

        if get_agent is not None:

            embed = Embed(
                title=get_agent.display_name,
                description=italics(get_agent.description_localizations.from_locale(str(locale))),
                colour=int(random.choice(get_agent.background_gradient_colors)[:-2], 16),
            )
            embed.set_image(url=get_agent.full_portrait)
            embed.set_thumbnail(url=get_agent.display_icon)
            embed.set_footer(
                text=get_agent.role.name_localizations.from_locale(str(locale)),
                icon_url=get_agent.role.display_icon,
            )

            # TODO: add agent abilities

            buttons = (
                ui.Button(label="Full Portrait", url=get_agent.full_portrait.url),
                ui.Button(label="Display Icon", url=get_agent.display_icon.url),
                ui.Button(label="Background", url=get_agent.background.url),
            )
            view = BaseView()
            for button in buttons:
                view.add_item(button)

            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(f"Could not find agent {bold(agent)}")

    @app_commands.command(name=_T('agents'), description=_T('Agent Contracts'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def agents(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)

        await self.v_client.set_authorize(v_user.get_1st())

        contracts = await self.v_client.fetch_contracts()

        agent_contract = contracts.special_contract()

        if agent_contract is None:
            return await interaction.followup.send("No active agent contract")

        print(agent_contract)

    @app_commands.command(name=_T('buddy'), description=_T('View buddy info'))
    @app_commands.guild_only()
    @app_commands.rename(buddy='buddy')
    @dynamic_cooldown(cooldown_5s)
    async def buddy(self, interaction: Interaction, buddy: str = None) -> None:

        await interaction.response.defer()

        locale = self.v_locale(interaction.locale)
        get_buddy = self.v_client.get_buddy_level(buddy)

        if get_buddy is not None:
            embed = Embed(colour=self.bot.theme.purple)

            if isinstance(get_buddy, Buddy):
                embed.set_author(
                    name=get_buddy.name_localizations.from_locale(str(locale)),
                    icon_url=get_buddy.theme.display_icon if get_buddy.theme is not None else None,
                    url=get_buddy.display_icon,
                )

            elif isinstance(get_buddy, BuddyLevel):
                embed.set_author(
                    name=get_buddy.get_base_buddy().name_localizations.from_locale(str(locale)),
                    url=get_buddy.display_icon,
                    icon_url=get_buddy.get_base_buddy().theme.display_icon
                    if get_buddy.get_base_buddy().theme is not None
                    else None,
                )
            embed.set_image(url=get_buddy.display_icon)

            view = BaseView()
            view.add_item(ui.Button(label="Display Icon", url=get_buddy.display_icon.url))

            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(f"Could not find buddy {bold(buddy)}")

    @app_commands.command(name=_T('bundle'), description='inspect a specific bundle')
    @app_commands.describe(bundle="The name of the bundle you want to inspect!")
    @app_commands.rename(bundle=_T('bundle'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def bundle(self, interaction: Interaction, bundle: str) -> None:

        await interaction.response.defer()

        locale = self.v_locale(interaction.locale)

        get_bundle = self.v_client.get_bundle(bundle)

        if get_bundle is not None:

            embeds = []

            embed = Embed(
                description=f"Featured Bundle: {bold(f'{get_bundle.name_localizations.from_locale(str(locale))} Collection')}\n"  # noqa: E501
                f"{PointEmoji.valorant_point} {get_bundle.price}",
                colour=self.bot.theme.purple,
            )
            if get_bundle.display_icon_2 is not None:
                embed.set_image(url=get_bundle.display_icon_2)

            embeds.append(embed)

            for item in sorted(get_bundle.items, key=lambda i: i.price, reverse=True):
                emoji = item.rarity.emoji if isinstance(item, Skin) else ''  # type: ignore
                e = Embed(
                    title=f"{emoji} {bold(item.name_localizations.from_locale(str(locale)))}",
                    description=f"{PointEmoji.valorant_point} {item.price}",
                    colour=self.bot.theme.dark,
                )

                if isinstance(item, PlayerCard):
                    item_icon = item.large_icon
                elif isinstance(item, Spray):
                    item_icon = item.full_transparent_icon or item.full_icon or item.display_icon
                else:
                    item_icon = item.display_icon

                if item_icon is not None:
                    e.url = item_icon.url
                    e.set_thumbnail(url=item_icon)

                embeds.append(e)

            await interaction.followup.send(embeds=embeds)

        else:

            await interaction.followup.send(f"Could not find bundle with name {bold(bundle)}")

    @app_commands.command(name=_T('spray'), description=_T('View spray info'))
    @app_commands.guild_only()
    @app_commands.rename(spray='spray')
    @dynamic_cooldown(cooldown_5s)
    async def spray(self, interaction: Interaction, spray: str = None) -> None:

        await interaction.response.defer()

        locale = self.v_locale(interaction.locale)
        get_spray = self.v_client.get_spray(spray)

        if get_spray is not None:
            embed = Embed(colour=self.bot.theme.purple)  # TODO: get color from spray
            view = BaseView()

            if isinstance(get_spray, Spray):
                embed.set_author(
                    name=get_spray.name_localizations.from_locale(str(locale)),
                    url=get_spray.display_icon,
                    icon_url=get_spray.theme.display_icon if get_spray.theme is not None else None,
                )
                embed.set_image(
                    url=get_spray.animation_gif or get_spray.full_transparent_icon or get_spray.display_icon
                )
                if get_spray.animation_gif:
                    view.add_item(ui.Button(label="Animation Gif", url=get_spray.animation_gif.url))
                if get_spray.full_transparent_icon:
                    view.add_item(
                        ui.Button(
                            label='Full Transparent Icon',
                            url=get_spray.full_transparent_icon.url,
                        )
                    )
                if get_spray.display_icon:
                    view.add_item(ui.Button(label='Display Icon', url=get_spray.display_icon.url))

            elif isinstance(get_spray, SprayLevel):
                base_spray = get_spray.get_base_spray()
                embed.set_author(
                    name=base_spray.name_localizations.from_locale(str(locale)),
                    icon_url=base_spray.theme.display_icon if base_spray.theme is not None else None,
                    url=get_spray.display_icon,
                )
                embed.set_image(
                    url=base_spray.animation_gif
                    or base_spray.full_transparent_icon
                    or base_spray.display_icon
                    or get_spray.display_icon
                )

                if base_spray.animation_gif:
                    view.add_item(ui.Button(label="Animation Gif", url=base_spray.animation_gif.url))
                if base_spray.full_transparent_icon:
                    view.add_item(
                        ui.Button(
                            label='Full Transparent Icon',
                            url=base_spray.full_transparent_icon.url,
                        )
                    )
                if base_spray.display_icon:
                    view.add_item(ui.Button(label="Display Icon", url=base_spray.display_icon.url))

            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(f"Could not find spray {bold(spray)}")

    player = app_commands.Group(name=_T('player'), description=_T('Player commands'), guild_only=True)

    @player.command(name=_T('card'), description=_T('View player card'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.rename(card='card')
    async def player_card(self, interaction: Interaction, card: str):

        await interaction.response.defer()

        locale = self.v_locale(interaction.locale)
        player_card = self.v_client.get_player_card(card)

        if player_card is not None:
            embed = Embed(colour=self.bot.theme.purple)
            embed.set_author(
                name=player_card.name_localizations.from_locale(str(locale)),
                icon_url=player_card.theme.display_icon if player_card.theme is not None else None,
                url=player_card.large_icon,
            )
            embed.set_image(url=player_card.large_icon)
            # TODO: player card views selection

            view = BaseView()
            if player_card.display_icon is not None:
                view.add_item(ui.Button(label="Display Icon", url=player_card.display_icon.url))

            await interaction.followup.send(embed=embed, view=view)

    @player.command(name=_T('title'), description=_T('View player title'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.rename(title='title')
    async def player_title(self, interaction: Interaction, title: str):

        await interaction.response.defer()

        locale = self.v_locale(interaction.locale)
        player_title = self.v_client.get_player_title(title)

        if player_title is not None:
            embed = Embed(colour=self.bot.theme.purple)

    @app_commands.command(name=_T('weapon'), description=_T('View weapon info'))
    @app_commands.guild_only()
    @app_commands.rename(weapon='weapon')
    @dynamic_cooldown(cooldown_5s)
    async def weapon(self, interaction: Interaction, weapon: str = None) -> None:
        ...

    @app_commands.command(name=_T('skin'), description=_T('View skin info'))
    @app_commands.guild_only()
    @app_commands.rename(skin='skin')
    @dynamic_cooldown(cooldown_5s)
    async def skin(self, interaction: Interaction, skin: str = None) -> None:
        ...

    # auto complete
    @bundle.autocomplete('bundle')
    @agent.autocomplete('agent')
    @buddy.autocomplete('buddy')
    @spray.autocomplete('spray')
    @weapon.autocomplete('weapon')
    @skin.autocomplete('skin')
    @player_card.autocomplete('card')
    @player_title.autocomplete('title')
    async def get_all_auto_complete(self, interaction: Interaction, current: str) -> List[Choice[str]]:

        locale = self.v_locale(interaction.locale)

        results: List[Choice[str]] = []
        mex_index = 25

        if interaction.command is self.bundle:

            bundle_list = self.get_all_bundles()
            namespace = interaction.namespace.bundle
            mex_index = 15

            for bundle in sorted(bundle_list, key=lambda a: a.name_localizations.from_locale(str(locale))):
                if bundle.name_localizations.from_locale(str(locale)).lower().startswith(namespace.lower()):

                    bundle_name = bundle.name_localizations.from_locale(str(locale))

                    index = 2
                    for choice in results:
                        if choice.name.startswith(bundle_name):
                            bundle_name = f"{bundle_name} {index}"
                            index += 1

                    results.append(app_commands.Choice(name=bundle_name, value=bundle.uuid))
                    if len(results) >= mex_index:
                        break

        else:

            if interaction.command is self.agent:
                value_list = self.get_all_agents()
                namespace = interaction.namespace.agent
            elif interaction.command is self.buddy:
                value_list = self.get_all_buddies()
                namespace = interaction.namespace.buddy
            elif interaction.command is self.spray:
                value_list = self.get_all_sprays()
                namespace = interaction.namespace.spray
            elif interaction.command is self.weapon:
                value_list = self.get_all_weapons()
                namespace = interaction.namespace.weapon
            elif interaction.command is self.skin:
                value_list = self.get_all_skins()
                namespace = interaction.namespace.skin
            elif interaction.command is self.player_card:
                value_list = self.get_all_player_cards()
                namespace = interaction.namespace.card
            elif interaction.command is self.player_title:
                value_list = self.get_all_player_titles()
                namespace = interaction.namespace.title
            else:
                return []

            for value in sorted(value_list, key=lambda a: a.name_localizations.from_locale(str(locale))):
                if value.name_localizations.from_locale(str(locale)).lower().startswith(namespace.lower()):

                    value_name = value.name_localizations.from_locale(str(locale))

                    if value_name == ' ':
                        continue

                    if not value_name.startswith('.') and not namespace.startswith('.'):
                        results.append(Choice(name=value_name, value=value.uuid))
                    elif namespace.startswith('.'):
                        results.append(Choice(name=value_name, value=value.uuid))

                if len(results) >= mex_index:
                    break

        return results[:mex_index]

    # @app_commands.command(name=_T('match'), description=_T('Last match history'))
    # @app_commands.choices(
    #     queue=[
    #         Choice(name=_T('Unrated'), value='unrated'),
    #         Choice(name=_T('Competitive'), value='competitive'),
    #         Choice(name=_T('Deathmatch'), value='deathmatch'),
    #         Choice(name=_T('Spike Rush'), value='spikerush'),
    #         Choice(name=_T('Escalation'), value='escalation'),
    #         Choice(name=_T('Replication'), value='replication'),
    #         Choice(name=_T('Snowball Fight'), value='snowball'),
    #         Choice(name=_T('Custom'), value='custom'),
    #     ]
    # )
    # @app_commands.describe(queue=_T('Choose the queue'))
    # @app_commands.rename(queue=_T('queue'))
    # @dynamic_cooldown(cooldown_5s)
    # @app_commands.guild_only()
    # async def match(self, interaction: Interaction, queue: Choice[str] = "null") -> None:
    #     await interaction.response.defer()
    #
    #     get_riot_acc = await self.get_riot_account(user_id=interaction.user.id)
    #     client = await self.v_client.set_authorize(get_riot_acc[0])
    #     match_history = await client.fetch_match_history(queue_id=QueueID.competitive)
    #
    #     if len(match_history) == 0:
    #         await interaction.followup.send('No match history found')
    #         return
    #
    #     view = MatchHistoryView(interaction, match_history.get_match_details())
    #     await view.start()

    # @app_commands.command(name=_T('stats'), description=_T('Show the stats of a player'))
    # @app_commands.choices(
    #     queue=[
    #         Choice(name=_T('Unrated'), value='unrated'),
    #         Choice(name=_T('Competitive'), value='competitive'),
    #         Choice(name=_T('Deathmatch'), value='deathmatch'),
    #         Choice(name=_T('Spike Rush'), value='spikerush'),
    #         Choice(name=_T('Escalation'), value='escalation'),
    #         Choice(name=_T('Replication'), value='replication'),
    #         Choice(name=_T('Snowball Fight'), value='snowball'),
    #         Choice(name=_T('Custom'), value='custom'),
    #     ]
    # )
    # @app_commands.describe(queue=_T('Choose the queue'))
    # @app_commands.rename(queue=_T('queue'))
    # @dynamic_cooldown(cooldown_5s)
    # @app_commands.guild_only()
    # async def stats(self, interaction: Interaction, queue: Choice[str] = "null") -> None:
    #     await interaction.response.defer()
    #
    #     view = StatsView(interaction)
    #     await view.pre_start()

    # @app_commands.command(name=_T('settings'), description=_T('Show the settings of the bot'))
    # async def settings(self, interaction: Interaction) -> None:
    #     ...

    # @app_commands.describe(queue=_T('Party commands'))
    # @dynamic_cooldown(cooldown_5s)
    # @app_commands.guild_only()
    # async def party(self, interaction: Interaction) -> None:
    #     await interaction.response.defer()

    # party = app_commands.Group(name=_T('party'), description=_T('Party commands'), guild_only=True)
    #
    # @party.command(name=_T('invite'), description=_T('Invite a player to your party'))
    # @dynamic_cooldown(cooldown_5s)
    # async def party_invite(self, interaction: Interaction, player: discord.User) -> None:
    #     ...
    #
    # @party.command(name=_T('invite_by_name'), description=_T('Invite a player to your party by name'))
    # @dynamic_cooldown(cooldown_5s)
    # async def party_invite_by_name(self, interaction: Interaction, player: str) -> None:
    #     ...
    #
    # @party.command(name=_T('kick'), description=_T('Kick a player from your party'))
    # @dynamic_cooldown(cooldown_5s)
    # async def party_kick(self, interaction: Interaction, player: discord.User) -> None:
    #     ...
    #
    # @party.command(name=_T('leave'), description=_T('Leave your party'))
    # @dynamic_cooldown(cooldown_5s)
    # async def party_leave(self, interaction: Interaction) -> None:
    #     ...

    # @app_commands.command(name=_T('leaderboard'), description=_T('Shows your Region Leaderboard'))
    # @app_commands.describe(region='Select region to get the leaderboard')
    # @dynamic_cooldown(cooldown_5s)
    # @app_commands.guild_only()
    # async def leaderboard(self, interaction: Interaction, region: Literal['AP', 'EU', 'NA', 'KR']) -> None:
    #     ...

    #
    # @app_commands.command(name=_T('profile'), description=_T('Shows your profile'))
    # @app_commands.guild_only()
    # async def profile(self, interaction: Interaction) -> None:
    #
    #     await interaction.response.defer()
    #
    #     riot_acc = await self.get_riot_account(user_id=interaction.user.id)
    #     client = await self.v_client.run(auth=riot_acc)
    #
    #     loadout = await client.fetch_player_loadout()
    #
    #     file = await profile_card(loadout)
    #
    #     embed = Embed(colour=0x63C0B5)
    #     embed.set_image(url="attachment://profile.png")
    #
    #     await interaction.followup.send(embed=embed, file=file)

    # @app_commands.command(name=_T('cookies'), description=_T('Log in with your Riot account by Cookies'))
    # @app_commands.describe(cookies=_T('Your cookies or SSID'))
    # @app_commands.rename(cookies=_T('cookies'))
    # @dynamic_cooldown(cooldown_5s)
    # @app_commands.guild_only()
    # async def cookies(self, interaction: Interaction, cookies: str) -> None:
    #
    #     await interaction.response.defer(ephemeral=True)
    #
    #     user_id = interaction.user.id
    #     guild_id = interaction.guild_id
    #
    #     try_auth = auth.Auth.redeem_cookies(cookies)
    #     if try_auth.auth_type == auth.AuthResponseType.response.value:
    #         authorize = auth.Auth.authorize(try_auth)
    #
    #         payload = dict(acc_num=1, **authorize.to_dict())
    #
    #         # encryption
    #         encrypt_payload = self.bot.encryption.encrypt(json.dumps(payload))
    #
    #         await self.bot.pool.execute(
    #             RIOT_ACC_WITH_UPSERT, user_id, guild_id, encrypt_payload, datetime.now(), user_id
    #         )
    #
    #         self.get_riot_account.invalidate(self, user_id)
    #
    #         e = Embed(description=f"Successfully logged in **{authorize.name}#{authorize.tagline}**")
    #         e.set_footer(text=f"token expires in 1 hour")
    #
    #         return await interaction.followup.send(embed=e)
    #
    #     raise CommandError("Invalid cookies")


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Valorant(bot))
