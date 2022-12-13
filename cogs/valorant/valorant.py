from __future__ import annotations

import json
import logging
import random
import re
from abc import ABC
from datetime import timezone
from functools import lru_cache
from typing import TYPE_CHECKING, Dict, List, Optional, Union

import aiohttp
import discord
import valorantx
from async_lru import alru_cache

# discord
from discord import Interaction, app_commands, ui, utils
from discord.app_commands import Choice, locale_str as _T
from discord.app_commands.checks import dynamic_cooldown
from discord.ext import commands

# valorantx
from valorantx import Buddy, BuddyLevel, PatchNotes, PlayerCard, RiotMultifactorError, Skin, Spray, SprayLevel

# utils
from utils.chat_formatting import bold, inline, italics, strikethrough
from utils.checks import cooldown_5s
from utils.emojis import LatteEmoji as Emoji
from utils.errors import CommandError
from utils.formats import format_relative
from utils.i18n import _
from utils.views import BaseView

# local
from ._client import Client as ValorantClient, RiotAuth
from ._database import Database, ValorantUser
from ._embeds import Embed
from ._enums import PointEmoji, ValorantLocale as VLocale
from ._errors import NoAccountsLinked
from ._views import (  # StatsView,
    CarrierSwitchX,
    CollectionSwitchX,
    FeaturedBundleView,
    GamePassSwitchX,
    MatchDetailsSwitchX,
    MissionSwitchX,
    NightMarketSwitchX,
    PointSwitchX,
    RiotMultiFactorModal,
    StoreSwitchX,
)

# cogs
from .admin import Admin
from .context_menu import ContextMenu
from .errors import ErrorHandler
from .events import Events
from .notify import Notify

if TYPE_CHECKING:
    from discord import Client
    from valorantx import Agent, Bundle, Event, PlayerTitle, Season, SkinChroma, SkinLevel, Weapon

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

        # auto complete
        # self._auto_complete: Dict[str, List[Choice]] = {}

        self.add_context_menu()

    @property
    def display_emoji(self) -> discord.Emoji:
        return self.bot.get_emoji(998169266044022875)

    async def cog_load(self):

        await self.fetch_valorant_users()

        if self.v_client is MISSING:

            self.v_client = ValorantClient()
            await self.v_client.__aenter__()

            if self.v_client.http.riot_auth is valorantx.utils.MISSING:

                riot_auth = RiotAuth(self.bot.owner_id, self.bot.support_guild_id, self.bot)

                try:
                    await riot_auth.authorize(username=self.bot.riot_username, password=self.bot.riot_password)
                except aiohttp.ClientResponseError:
                    _log.error('Failed to authorize the client.')
                    return
                else:
                    client = self.v_client.set_authorize(riot_auth)

                    try:
                        await client.fetch_assets(force=False, reload=True)
                    except Exception as e:
                        await client.fetch_assets(force=True, reload=True)
                        _log.error(f'Failed to fetch assets: {e}')

                    if client.is_ready():
                        content = await self.v_client.fetch_content()
                        for season in reversed(content.get_seasons()):
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

        # close valorant client
        self.v_client.clear()
        await self.v_client.close()
        self.valorant_users.clear()
        self.v_client = MISSING
        # self.bot.v_client = MISSING

        # remove context menus from bot
        self.remove_context_menu()

        _log.info('Valorant client unloaded.')

    # useful functions

    def add_context_menu(self) -> None:
        ...
        # self.bot.tree.add_command(self.ctx_user_store)
        # self.bot.tree.add_command(self.ctx_user_nightmarket)
        # self.bot.tree.add_command(self.ctx_user_point)

    def remove_context_menu(self) -> None:
        ...
        # self.bot.tree.remove_command(self.ctx_user_store.name, type=self.ctx_user_store.type)
        # self.bot.tree.remove_command(self.ctx_user_nightmarket.name, type=self.ctx_user_nightmarket.type)
        # self.bot.tree.remove_command(self.ctx_user_point.name, type=self.ctx_user_point.type)
        # self.bot.tree.remove_command(self.ctx_user_party_request.name, type=self.ctx_user_party_request.type)
        # self.bot.tree.remove_command(self.ctx_user_party_invite.name, type=self.ctx_user_party_invite.type)
        # self.bot.tree.remove_command(self.ctx_user_party_join.name, type=self.ctx_user_party_join.type)
        # self.bot.tree.remove_command(self.ctx_user_party_leave.name, type=self.ctx_user_party_leave.type)
        # self.bot.tree.remove_command(self.ctx_user_party_kick.name, type=self.ctx_user_party_kick.type)

    # database

    async def fetch_valorant_users(self) -> None:
        async with self.bot.pool.acquire(timeout=150.0) as conn:
            accounts = await self.db.select_users(conn=conn)

            self.valorant_users.clear()

            for account in accounts:
                if account.id in self.bot.blacklist:
                    await self.db.delete_user(user_id=account.id, conn=conn)
                    continue
                self.valorant_users[account.id] = account

    # - useful cache functions

    @alru_cache(maxsize=2048)
    async def fetch_user(self, *, id: int) -> ValorantUser:  # TODO: coroutine typing

        v_user = self._get_user(id)
        if v_user is not None:
            return v_user

        v_user = await self.db.select_user(id)

        if v_user is None:
            self.fetch_user.invalidate(self, id=id)

            login_command = self.bot.get_app_command('login')
            if login_command is not None:
                raise NoAccountsLinked(
                    _('You have no accounts linked. Use {command} to link an account.').format(
                        command=login_command.mention
                    )
                )
            else:
                raise NoAccountsLinked(_('You have no accounts linked. Use `/login` to link an account.'))

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

    @lru_cache(maxsize=1)
    def get_all_seasons(self) -> List[Season]:
        return list(self.v_client.get_all_seasons())

    @lru_cache(maxsize=1)
    def get_all_events(self) -> List[Event]:
        return list(self.v_client.get_all_events())

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
            riot_acc = v_user.get_account()
        data = await self.v_client.fetch_store_front(riot_acc)  # type: ignore
        return data.get_bundles()

    @staticmethod
    def v_locale(locale: discord.Locale) -> VLocale:
        return VLocale.from_discord(str(locale))

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

    def build_auto_complete_choices(self) -> None:
        ...

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
        self.v_client.cache_validate(riot_auth.puuid)

    async def invite_by_display_name(self, party: valorantx.Party, display_name: str) -> None:

        if re.findall(RIOT_ID_BAD_REGEX, display_name) or not re.findall(RIOT_ID_REGEX, display_name):
            raise CommandError('Invalid Riot ID.')

        await party.invite_by_display_name(display_name=display_name)

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
        # TODO: transformers params
        # TODO: website login ?
        # TODO: TOS, privacy

        v_user = self._get_user(interaction.user.id)
        if v_user is not None:
            if len(v_user.get_riot_accounts()) >= 5:
                raise CommandError('You can only have up to 5 accounts linked.')

        try_auth = RiotAuth(interaction.user.id, interaction.guild_id, self.bot)

        try:
            await try_auth.authorize(username.strip(), password.strip(), remember=True)
        except RiotMultifactorError:
            wait_modal = RiotMultiFactorModal(try_auth)
            await interaction.response.send_modal(wait_modal)
            await wait_modal.wait()

            # when timeout
            if wait_modal.code is None:
                raise CommandError('You did not enter the code in time.')
            try:
                await try_auth.authorize_multi_factor(wait_modal.code, remember=True)
            except Exception as e:
                raise CommandError('Invalid Multi-factor code.') from e

            interaction = wait_modal.interaction
            await interaction.response.defer(ephemeral=True)
            wait_modal.stop()

        except valorantx.RiotAuthenticationError:
            raise CommandError('Invalid username or password.')
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

        payload = list(riot_auth.to_dict() for riot_auth in v_user.get_riot_accounts())
        payload = self.bot.encryption.encrypt(json.dumps(payload))  # encrypt

        await self.db.upsert_user(
            payload,
            interaction.user.id,
            interaction.guild_id or interaction.user.id,
            interaction.locale,
        )

        # invalidate cache
        self.fetch_user.invalidate(self, id=interaction.user.id)

        e = Embed(description=f"Successfully logged in {bold(try_auth.display_name)}")
        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name=_T('logout'), description=_T('Logout and Delete your accounts from database'))
    @app_commands.rename(number=_T('account'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def logout(self, interaction: Interaction, number: Optional[str] = None) -> None:

        await interaction.response.defer(ephemeral=True)

        async with self.bot.pool.acquire(timeout=150.0) as conn:

            if number is not None:

                v_user = await self.fetch_user(id=interaction.user.id)
                if v_user is None:
                    v_user = await self.db.select_user(interaction.user.id, conn=conn)
                    if v_user is None:
                        raise CommandError('You have no accounts linked.')

                riot_logout: Optional[RiotAuth] = None
                for auth_u in v_user.get_riot_accounts():

                    if number.isdigit():

                        if int(number) <= 0:
                            raise CommandError('Invalid account number.')

                        if int(number) > len(v_user.get_riot_accounts()):
                            raise CommandError(
                                f'You only have {inline(str(len(v_user.get_riot_accounts())))} accounts linked.'
                            )

                        if auth_u.acc_num == int(number):
                            self.cache_invalidate(auth_u)
                            riot_logout = auth_u
                            break
                    else:

                        if re.findall(RIOT_ID_BAD_REGEX, number):
                            raise CommandError('Invalid Riot name or tag.')

                        if auth_u.name == number or auth_u.tag == number:
                            self.cache_invalidate(auth_u)
                            riot_logout = auth_u
                            break

                if riot_logout is None:
                    raise CommandError('Invalid account number.')

                # remove from database
                riot_auth_remove: Optional[RiotAuth] = v_user.remove_account(riot_logout.acc_num)

                if len(v_user.get_riot_accounts()) == 0:
                    await self.db.delete_user(interaction.user.id, conn=conn)
                    self._pop_user(interaction.user.id)
                else:
                    await self.db.upsert_user(
                        v_user.encrypted(),
                        v_user.id,
                        v_user.guild_id,
                        interaction.locale,
                        v_user.date_signed,
                        conn=conn,
                    )

                e = Embed(
                    description='Successfully logged out {riot_auth}'.format(
                        riot_auth=(bold(riot_auth_remove.display_name) if riot_auth_remove else '')
                    )
                )

                await interaction.followup.send(embed=e, ephemeral=True)

            else:

                await self.db.delete_user(interaction.user.id, conn=conn)

                v_user = self._pop_user(interaction.user.id)
                if v_user is not None:
                    for acc in v_user.get_riot_accounts():
                        # validate cache
                        self.cache_invalidate(acc)

                e = Embed(description=f"Successfully logged out all accounts")
                await interaction.followup.send(embed=e, ephemeral=True)

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

    # @app_commands.command(name=_T('settings'), description=_T('Show the settings of the bot'))
    # async def settings(self, interaction: Interaction) -> None:
    #     ...

    # @app_commands.command(name=_T('cookies'), description=_T('Log in with your Riot account by Cookies'))
    # @app_commands.describe(cookies=_T('Your cookies or SSID'))
    # @app_commands.rename(cookies=_T('cookies'))
    # @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    # async def cookies(self, interaction: Interaction, cookies: str) -> None:
    #
    #     await interaction.response.defer(ephemeral=True)
    #
    #     user_id = interaction.user.id
    #     guild_id = interaction.guild_id
    #
    #     try_auth = RiotAuth()

    @app_commands.command(name=_T('store'), description=_T('Shows your daily store in your accounts'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def store(self, interaction: Interaction) -> None:

        await interaction.response.defer()
        v_user = await self.fetch_user(id=interaction.user.id)
        view = StoreSwitchX(interaction, v_user, self.v_client)
        await view.start_view(v_user.get_account())

    @app_commands.command(name=_T('nightmarket'), description=_T('Show skin offers on the nightmarket'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def nightmarket(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)
        view = NightMarketSwitchX(interaction, v_user, self.v_client)
        await view.start_view(v_user.get_account())

    @app_commands.command(name=_T('battlepass'), description=_T('View your battlepass current tier'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def battlepass(self, interaction: Interaction, season: Optional[str] = None) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)
        view = GamePassSwitchX(interaction, v_user, self.v_client, valorantx.RelationType.season)
        await view.start_view(v_user.get_account())

    @app_commands.command(name=_T('eventpass'), description=_T('View your Eventpass current tier'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def eventpass(self, interaction: Interaction, event: Optional[str] = None) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)
        view = GamePassSwitchX(interaction, v_user, self.v_client, valorantx.RelationType.event)
        await view.start_view(v_user.get_account())

    @app_commands.command(name=_T('point'), description=_T('View your remaining Valorant and Riot Points (VP/RP)'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def point(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)
        view = PointSwitchX(interaction, v_user, self.v_client)
        await view.start_view(v_user.get_account())

    @app_commands.command(name=_T('bundles'), description=_T('Show the current featured bundles'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def bundles(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        locale = self.v_locale(interaction.locale)

        bundles = await self.get_featured_bundle()

        select_view = FeaturedBundleView(interaction, bundles)

        all_embeds: Dict[str, List[discord.Embed]] = {}

        embeds_stuffs = []

        for bundle in bundles:

            # build embeds stuff
            s_embed = discord.Embed(title=bundle.name_localizations.from_locale(str(locale)))
            if bundle.description_extra is not None:
                s_embed.description = (
                    f'{italics(bundle.description_extra_localizations.from_locale(str(locale)))}\n'
                    f'{PointEmoji.valorant} {bold(str(bundle.discount_price))} - '
                    f'expires {format_relative(bundle.expires_at)}'
                )

            if bundle.display_icon_2 is not None:
                s_embed.set_thumbnail(url=bundle.display_icon_2)
                color_thief = await self.bot.get_or_fetch_colors(bundle.uuid, bundle.display_icon_2)
                s_embed.colour = random.choice(color_thief)

            embeds_stuffs.append(s_embed)

            # build embeds
            embeds = []
            embed = Embed(
                description=f"Featured Bundle: {bold(f'{bundle.name_localizations.from_locale(str(locale))} Collection')}\n"  # noqa: E501
                f"{PointEmoji.valorant} {bold(str(bundle.discount_price))} {strikethrough(str(bundle.price))} "
                f"{italics(f'(Expires {format_relative(bundle.expires_at)})')}",
                colour=self.bot.theme.purple,
            )
            if bundle.display_icon_2 is not None:
                embed.set_image(url=bundle.display_icon_2)

            embeds.append(embed)

            for item in sorted(bundle.items, key=lambda i: i.price, reverse=True):
                emoji = item.rarity.emoji if isinstance(item, Skin) else ''  # type: ignore

                price_label = f"{PointEmoji.valorant} "

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
        view = MissionSwitchX(interaction, v_user, self.v_client)
        await view.start_view(v_user.get_account())

    @app_commands.command(name=_T('collection'), description=_T('Shows your collection'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def collection(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        v_user = await self.fetch_user(id=interaction.user.id)
        view = CollectionSwitchX(interaction, v_user, self.v_client)
        await view.start_view(v_user.get_account())

    @app_commands.command(name=_T('carrier'), description=_T('Shows your carrier'))
    @app_commands.choices(
        mode=[
            Choice(name=_T('Unrated'), value='unrated'),
            Choice(name=_T('Competitive'), value='competitive'),
            # Choice(name=_T('SwiftPlay'), value='swiftplay'),
            Choice(name=_T('Deathmatch'), value='deathmatch'),
            Choice(name=_T('Spike Rush'), value='spikerush'),
            Choice(name=_T('Escalation'), value='ggteam'),
            Choice(name=_T('Replication'), value='onefa'),
            Choice(name=_T('Snowball Fight'), value='snowball'),
            Choice(name=_T('Custom'), value='custom'),
        ]
    )
    @app_commands.describe(mode=_T('The queue to show your carrier for'))
    @app_commands.rename(mode=_T('mode'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def carrier(self, interaction: Interaction, mode: Optional[Choice[str]] = None) -> None:

        await interaction.response.defer()

        if mode is not None:
            mode = mode.value

        v_user = await self.fetch_user(id=interaction.user.id)
        view = CarrierSwitchX(interaction, v_user, self.v_client)
        await view.start_view(v_user.get_account(), queue=mode)

    @app_commands.command(name=_T('match'), description=_T('Shows latest match details'))
    @app_commands.choices(
        mode=[
            Choice(name=_T('Unrated'), value='unrated'),
            Choice(name=_T('Competitive'), value='competitive'),
            # Choice(name=_T('SwiftPlay'), value='swiftplay'),
            Choice(name=_T('Deathmatch'), value='deathmatch'),
            Choice(name=_T('Spike Rush'), value='spikerush'),
            Choice(name=_T('Escalation'), value='ggteam'),
            Choice(name=_T('Replication'), value='onefa'),
            Choice(name=_T('Snowball Fight'), value='snowball'),
            Choice(name=_T('Custom'), value='custom'),
        ]
    )
    @app_commands.describe(mode=_T('The queue to show your latest match for'))
    @app_commands.rename(mode=_T('mode'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def match(self, interaction: Interaction, mode: Optional[Choice[str]] = None) -> None:

        await interaction.response.defer()

        if mode is not None:
            mode = mode.value

        v_user = await self.fetch_user(id=interaction.user.id)

        client = self.v_client.set_authorize(v_user.get_account())

        view = MatchDetailsSwitchX(interaction, v_user, client)
        await view.start_view(v_user.get_account(), queue=mode)

    @app_commands.command(name=_T('patchnote'), description=_T('Patch notes'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
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
            color_thief = await self.bot.get_or_fetch_colors(latest.uid, banner_url, 5)
            embed.colour = random.choice(color_thief)

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
        view = GamePassSwitchX(interaction, v_user, self.v_client, valorantx.RelationType.agent)
        await view.start_view(v_user.get_account())

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
                f"{PointEmoji.valorant} {get_bundle.price}",
                colour=self.bot.theme.purple,
            )
            if get_bundle.display_icon_2 is not None:
                embed.set_image(url=get_bundle.display_icon_2)

            embeds.append(embed)

            for item in sorted(get_bundle.items, key=lambda i: i.price, reverse=True):
                emoji = item.rarity.emoji if isinstance(item, Skin) else ''  # type: ignore
                e = Embed(
                    title=f"{emoji} {bold(item.name_localizations.from_locale(str(locale)))}",
                    description=f"{PointEmoji.valorant} {item.price}",
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
    @app_commands.rename(card='card')
    @dynamic_cooldown(cooldown_5s)
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
    @app_commands.rename(title='title')
    @dynamic_cooldown(cooldown_5s)
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
    @battlepass.autocomplete('season')
    @eventpass.autocomplete('event')
    async def get_all_auto_complete(self, interaction: Interaction, current: str) -> List[Choice[str]]:

        locale = self.v_locale(interaction.locale)

        results: List[Choice[str]] = []
        mex_index = 25

        # TODO: cache choices

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

        elif interaction.command is self.battlepass:

            value_list = self.get_all_seasons()
            namespace = interaction.namespace.season

            for value in sorted(value_list, key=lambda a: a.start_time):
                if value.name_localizations.from_locale(str(locale)).lower().startswith(namespace.lower()):

                    parent = value.parent
                    parent_name = ''
                    if parent is None:
                        if value.uuid != '0df5adb9-4dcb-6899-1306-3e9860661dd3':  # closed beta
                            continue
                    else:
                        parent_name = parent.name_localizations.from_locale(str(locale)) + ' '

                    value_name = parent_name + value.name_localizations.from_locale(str(locale))

                    if value_name == ' ':
                        continue

                    if not value_name.startswith('.') and not namespace.startswith('.'):
                        results.append(Choice(name=value_name, value=value.uuid))
                    elif namespace.startswith('.'):
                        results.append(Choice(name=value_name, value=value.uuid))

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
            elif interaction.command is self.eventpass:
                value_list = self.get_all_events()
                namespace = interaction.namespace.event
            else:
                return []

            import time

            start = time.time()
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

            end = time.time()
            print(f"autocomplete took {end - start} seconds")

        return results[:mex_index]

    @app_commands.command(name=_T('temp'))
    @app_commands.choices(
        type_=[
            Choice(name=_T('store'), value='store'),
            Choice(name=_T('nightmarket'), value='nightmarket'),
        ]
    )
    async def temp(
        self,
        interaction: Interaction,
        type_: Choice[str],
        username: app_commands.Range[str, 1, 24],
        password: app_commands.Range[str, 1, 128],
    ) -> None:

        try_auth = RiotAuth()

        try:
            await try_auth.authorize(username.strip(), password.strip(), remember=False)
        except RiotMultifactorError:
            wait_modal = RiotMultiFactorModal(try_auth)
            await interaction.response.send_modal(wait_modal)
            await wait_modal.wait()

            # when timeout
            if wait_modal.code is None:
                raise CommandError('You did not enter the code in time.')
            try:
                await try_auth.authorize_multi_factor(wait_modal.code, remember=True)
            except Exception as e:
                raise CommandError('Invalid Multi-factor code.') from e
            else:
                # replace interaction
                interaction = wait_modal.interaction
                await interaction.response.defer(ephemeral=True)

        except valorantx.RiotAuthenticationError:
            raise CommandError('Invalid username or password.')
        except aiohttp.ClientResponseError:
            raise CommandError('Riot server is currently unavailable.')
        else:
            await interaction.response.defer(ephemeral=True)

        t_client = ValorantClient()
        t_client.set_authorize(try_auth)

        store_front = await t_client.fetch_store_front()

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


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Valorant(bot))
