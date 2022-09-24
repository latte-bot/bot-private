from __future__ import annotations

import io
import json
import logging
import random
from abc import ABC
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING, Dict, List, Literal, Union

import aiohttp
import discord
import valorant
from async_lru import alru_cache
from colorthief import ColorThief

# discord
from discord import Interaction, app_commands, ui, utils
from discord.app_commands import Choice, locale_str as _T
from discord.app_commands.checks import dynamic_cooldown
from discord.ext import commands

# valorant
from valorant.errors import RiotMultifactorError
from valorant.models import Buddy, BuddyLevel, PlayerCard, Skin, Spray, SprayLevel

from utils.chat_formatting import bold, italics, strikethrough

# utils
from utils.checks import cooldown_5s
from utils.errors import CommandError
from utils.formats import format_relative
from utils.views import BaseView

# usually
from ._client import Client as ValorantClient, RiotAuth
from ._embeds import Embed
from ._enums import ContentTier as ContentTierEmoji, Point as PointEmoji, ValorantLocale as VLocale
from ._errors import NoAccountsLinked
from ._pillow import player_collection, profile_card
from ._sql_statements import ACCOUNT_DELETE, ACCOUNT_SELECT, ACCOUNT_SELECT_ALL, ACCOUNT_WITH_UPSERT
from ._views import FeaturedBundleView, RiotMultiFactorModal, SwitchAccountView

# cogs
from .admin import Admin
from .context_menu import ContextMenu
from .errors import ErrorHandler
from .events import Events
from .notify import Notify

if TYPE_CHECKING:
    from discord import Client
    from valorant import Agent, Bundle, PlayerTitle, SkinChroma, SkinLevel, Weapon

    from bot import LatteBot

    ClientBot = Union[Client, LatteBot]

_log = logging.getLogger(__name__)

MISSING = utils.MISSING


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
        self.bot: LatteBot = bot

        # users
        self.users: Dict[int, List[RiotAuth]] = {}

        # color cache
        self.patch_note_color: Dict[str, int] = {}
        self.featured_bundle_color: Dict[str, int] = {}

        # context menu
        self.ctx_user_store = app_commands.ContextMenu(
            name=_T('store'),
            callback=self.store_user_context,
        )
        self.ctx_user_nightmarket = app_commands.ContextMenu(
            name=_T('nightmarket'),
            callback=self.nightmarket_user_context,
        )
        self.ctx_user_point = app_commands.ContextMenu(
            name=_T('point'),
            callback=self.point_user_context,
        )

        # add context menus to bot
        self.bot.tree.add_command(self.ctx_user_store)
        self.bot.tree.add_command(self.ctx_user_nightmarket)
        self.bot.tree.add_command(self.ctx_user_point)

    @property
    def display_emoji(self) -> discord.Emoji:
        return self.bot.get_emoji(998169266044022875)

    async def cog_load(self):

        if self.v_client is MISSING:
            self.v_client = ValorantClient()

            if self.v_client.http._riot_auth is valorant.utils.MISSING:
                riot_acc = await self.get_riot_account(user_id=self.bot.owner_id)
                await self.v_client.set_authorize(riot_acc[0])

            try:
                await self.v_client.fetch_assets(with_price=True, force=True, reload=True)
            except Exception as e:
                await self.v_client.fetch_assets(force=True, reload=True)
                _log.error(f'Failed to fetch assets with price: {e}')
            finally:
                _log.info('Valorant client loaded.')

        await self.load_cache_from_database()

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
        self.bot.tree.remove_command(self.ctx_user_store.name, type=self.ctx_user_store.type)
        self.bot.tree.remove_command(self.ctx_user_nightmarket.name, type=self.ctx_user_nightmarket.type)
        self.bot.tree.remove_command(self.ctx_user_point.name, type=self.ctx_user_point.type)

        # close valorant client
        await self.v_client.close()
        self.v_client = MISSING

        # clear users
        self.users.clear()

        _log.info('Valorant client unloaded.')

    # useful functions

    async def load_cache_from_database(self) -> None:
        async with self.bot.pool.acquire(timeout=150.0) as conn:
            data = await conn.fetch(ACCOUNT_SELECT_ALL)
            for row in data:
                data = self.bot.encryption.decrypt(row['extras'])
                data_dict = json.loads(data)
                self.users[row['user_id']] = []
                for user_acc in data_dict:
                    riot_acc = RiotAuth(row['user_id'], bot=self.bot)
                    riot_acc.guild_id = row['guild_id']
                    riot_acc.date_signed = row['date_signed']
                    await riot_acc.from_dict(user_acc)
                    self.users[row['user_id']].append(riot_acc)

    # - useful cache functions

    @alru_cache(maxsize=1024)  # TODO: 1024 may be too much?
    async def get_riot_account(self, *, user_id: int) -> List[RiotAuth]:

        riot_acc = self.users.get(user_id)
        if riot_acc is not None:
            return riot_acc

        row = await self.bot.pool.fetchrow(ACCOUNT_SELECT, user_id)

        if row is None:
            self.get_riot_account.invalidate(self, user_id=user_id)
            raise NoAccountsLinked('You have no accounts linked.')

        data = self.bot.encryption.decrypt(row['extras'])

        data_dict = json.loads(data)

        self.users[user_id] = []
        for user_acc in data_dict:
            riot_auth = RiotAuth(user_id, bot=self.bot)
            riot_auth.guild_id = row['guild_id']
            await riot_auth.from_dict(user_acc)
            self.users[user_id].append(riot_auth)

        riot_acc = self.users.get(user_id)
        if riot_acc is None:
            self.get_riot_account.invalidate(self, user_id=user_id)
            if user_id == self.bot.owner_id:
                riot_acc = RiotAuth(self.bot.owner_id, bot=self.bot)
                riot_acc.guild_id = self.bot.support_guild_id
                await riot_acc.authorize(username=self.bot.riot_username, password=self.bot.riot_password)
            raise NoAccountsLinked('You have no accounts linked.')

        return riot_acc

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
    async def get_patch_notes(self, locale: discord.Locale) -> valorant.PatchNotes:
        return await self.v_client.fetch_patch_notes(self.locale_converter(locale))

    @alru_cache(maxsize=1)
    async def get_featured_bundle(self) -> List[valorant.FeaturedBundle]:
        try:
            riot_acc = await self.get_riot_account(user_id=self.bot.owner_id)  # super user
        except NoAccountsLinked:
            riot_acc = RiotAuth(self.bot.owner_id, bot=self.bot)
            riot_acc.guild_id = self.bot.support_guild_id
            await riot_acc.authorize(username=self.bot.riot_username, password=self.bot.riot_password)
        else:
            riot_acc = riot_acc[0]
        client = await self.v_client.set_authorize(riot_acc)
        data = await client.fetch_store_front()
        return data.bundles

    @staticmethod
    def locale_converter(locale: discord.Locale) -> str:
        return VLocale.from_discord(str(locale))

    def clear_cache_assets(self):
        self.get_riot_account.cache_clear()
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

    # functions

    @alru_cache(maxsize=1024)
    async def get_store(self, riot_acc: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US) -> List[discord.Embed]:

        client = await self.v_client.set_authorize(riot_acc)
        data = await client.fetch_store_front()

        embeds = [
            Embed(
                description=f"Daily store for {bold(client.user.display_name)}\n"
                f"Resets {format_relative(data.store.reset_at)}"
            )
        ]

        for skin in data.store.skins:
            emoji = ContentTierEmoji.from_name(skin.rarity.dev_name)
            e = Embed(
                title=f"{emoji} {bold(skin.name_localizations.from_locale_code(str(locale)))}",
                description=f"{PointEmoji.valorant_point} {skin.price}",
                colour=self.bot.theme.dark,
            )
            if skin.display_icon is not None:
                e.url = skin.display_icon.url
                e.set_thumbnail(url=skin.display_icon)
            embeds.append(e)

        return embeds

    @alru_cache(maxsize=1024)
    async def get_battlepass(
        self, riot_acc: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US
    ) -> List[discord.Embed]:

        client = await self.v_client.set_authorize(riot_acc)
        contract = await client.fetch_contracts()

        btp = contract.get_latest_contract(relation_type=valorant.RelationType.season)

        next_reward = btp.next_tier_reward.reward

        embed = discord.Embed(
            title=f"Battlepass for {bold(client.user.display_name)}",
            description=f"{bold('NEXT')}: {next_reward.display_name}",
        )
        embed.set_footer(text=f'TIER {btp.current_tier} | {btp.name_localizations.from_locale_code(str(locale))}')

        if next_reward is not None:
            if next_reward is not None:
                if next_reward.display_icon is not None:
                    if isinstance(next_reward, valorant.SkinLevel):
                        embed.set_image(url=next_reward.display_icon)
                    elif isinstance(next_reward, valorant.PlayerCard):
                        embed.set_image(url=next_reward.wide_icon)
                    else:
                        embed.set_thumbnail(url=next_reward.display_icon)

        if btp.current_tier <= 50:
            embed.colour = self.bot.theme.purple
        else:
            embed.colour = self.bot.theme.gold

        return [embed]

    @alru_cache(maxsize=1024)
    async def get_nightmarket(
        self, riot_acc: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US
    ) -> List[discord.Embed]:

        client = await self.v_client.set_authorize(riot_acc)
        data = await client.fetch_store_front()

        if data.nightmarket is None:
            raise CommandError(f"{bold('Nightmarket')} is not available.")

        embeds = [
            Embed(
                description=f"NightMarket for {bold(client.user.display_name)}\n"
                f"Expires {format_relative(data.nightmarket.expire_at)}",
                colour=self.bot.theme.purple,
            )
        ]

        for skin in data.nightmarket.skins:
            emoji = ContentTierEmoji.from_name(skin.rarity.dev_name)
            e = Embed(
                title=f"{emoji} {bold(skin.name_localizations.from_locale_code(locale))}",
                description=f"{PointEmoji.valorant_point} {bold(str(skin.discount_price))}\n"
                f"{PointEmoji.valorant_point}  {strikethrough(str(skin.price))} (-{skin.discount_percent}%)",
                colour=self.bot.theme.dark,
            )
            if skin.display_icon is not None:
                e.url = skin.display_icon.url
                e.set_thumbnail(url=skin.display_icon)
            embeds.append(e)

        return embeds

    @alru_cache(maxsize=1024)
    async def get_point(self, riot_acc: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US) -> List[discord.Embed]:

        client = await self.v_client.set_authorize(riot_acc)
        wallet = await client.fetch_wallet()

        vp = client.get_currency(uuid='85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741')
        rad = client.get_currency(uuid='e59aa87c-4cbf-517a-5983-6e81511be9b7')

        vp_display_name = vp.name_localizations.from_locale_code(locale)

        embed = Embed(title=f"{client.user.display_name} Point:")
        embed.add_field(
            name=f"{(vp_display_name if vp_display_name != 'VP' else 'Valorant Points')}",
            value=f"{PointEmoji.valorant_point} {wallet.valorant_points}",
        )
        embed.add_field(
            name=f'{rad.name_localizations.from_locale_code(locale)}',
            value=f"{PointEmoji.radianite_point} {wallet.radiant_points}",
        )

        return [embed]

    # @alru_cache(maxsize=1024)
    # def get_mission(self, riot_acc: RiotAuth, locale: Union[VLocale, str] = VLocale.en_US) -> List[discord.Embed]:
    #
    #     client = await self.v_client.set_authorize(riot_acc)
    #     contracts = await client.fetch_contracts()
    #
    #     embeds = []
    #
    #     for mission in contracts.missions:
    #         embed = Embed(title=mission.title_localizations.from_locale_code(locale))
    #         embed.add_field(name="Progress", value=f"{mission.progress}/{mission.goal}")
    #         embed.add_field(name="Reward", value=f"{mission.reward}")
    #         embeds.append(embed)
    #
    #     return embeds

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

        if len(self.users.get(interaction.user.id, [])) >= 5:
            raise CommandError('You can only have up to 5 accounts linked.')

        try_auth = RiotAuth(interaction.user.id, bot=self.bot)
        try_auth.guild_id = interaction.guild_id

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

        get_user = self.users.get(interaction.user.id)
        if get_user is None:
            try_auth.acc_num = 1
            self.users[interaction.user.id] = [try_auth]
        else:
            for auth_u in get_user:
                if auth_u.puuid == try_auth.puuid:
                    raise CommandError('You already have this account linked.')
            try_auth.acc_num = len(get_user) + 1
            self.users[interaction.user.id].append(try_auth)

        # insert to database sql and encrypt data

        user_data = self.users[interaction.user.id]
        payload = [user_riot_auth.to_dict() for user_riot_auth in user_data]
        dumps_payload = json.dumps(payload)

        # encryption
        encrypt_payload = self.bot.encryption.encrypt(dumps_payload)

        await self.bot.pool.execute(
            ACCOUNT_WITH_UPSERT,
            interaction.user.id,
            interaction.guild_id,
            encrypt_payload,
            datetime.now(),
            interaction.user.id,
        )

        # invalidate cache
        self.get_riot_account.invalidate(self, user_id=interaction.user.id)

        e = Embed(description=f"Successfully logged in {bold(try_auth.display_name)}")

        await interaction.followup.send(embed=e, ephemeral=True)

    @app_commands.command(name=_T('logout'), description=_T('Logout and Delete your accounts from database'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def logout(self, interaction: Interaction, number: app_commands.Range[int, 1, 5] = 0) -> None:

        await interaction.response.defer()

        async with self.bot.pool.acquire(timeout=150.0) as conn:

            if number != 0:
                data = await conn.fetchrow(ACCOUNT_SELECT, interaction.user.id)

                if data is None or self.users.get(interaction.user.id) is None:
                    raise CommandError('You have no accounts linked.')

                data = self.bot.encryption.decrypt(data['extras'])
                data_dict = json.loads(data)

                # remove from database
                for user_acc in data_dict:
                    if user_acc['acc_num'] == number:
                        data_dict.remove(user_acc)
                        break

                # to_json
                payload = json.dumps(data_dict)

                # encryption
                encrypt_payload = self.bot.encryption.encrypt(payload)

                await conn.execute(
                    ACCOUNT_WITH_UPSERT,
                    interaction.user.id,
                    interaction.guild_id,
                    encrypt_payload,
                    datetime.now(),
                    interaction.user.id,
                )

                # remove for cache

                data_cache = self.users.get(interaction.user.id)
                acc_remove = None
                if data_cache is not None:
                    for user_acc in data_cache:
                        if user_acc.acc_num == number:
                            acc_remove = user_acc
                            data_cache.remove(user_acc)
                            break

                e = Embed(description=f"Successfully logged out {bold(acc_remove.display_name)}")

                await interaction.followup.send(embed=e, ephemeral=True)

            else:
                await conn.execute(ACCOUNT_DELETE, interaction.user.id)
                self.users.pop(interaction.user.id, None)

                e = Embed(description=f"Successfully logged out all accounts")

                await interaction.followup.send(embed=e, ephemeral=True)

        # invalidate cache
        self.get_riot_account.invalidate(self, user_id=interaction.user.id)

    @app_commands.command(name=_T('store'), description=_T('Shows your daily store in your accounts'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def store(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        riot_acc = await self.get_riot_account(user_id=interaction.user.id)

        embeds = await self.get_store(riot_acc[0], self.locale_converter(interaction.locale))

        switch_view = SwitchAccountView(interaction, riot_acc, self.get_store)
        await interaction.followup.send(embeds=embeds, view=switch_view)

    @app_commands.command(name=_T('nightmarket'), description=_T('Show skin offers on the nightmarket'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.rename(hide=_T('hide'))
    @app_commands.guild_only()
    async def nightmarket(self, interaction: Interaction, hide: bool = False) -> None:

        await interaction.response.defer()

        riot_acc = await self.get_riot_account(user_id=interaction.user.id)

        embeds = await self.get_nightmarket(riot_acc[0], self.locale_converter(interaction.locale))

        switch_view = SwitchAccountView(interaction, riot_acc, self.get_nightmarket)
        await interaction.followup.send(embeds=embeds, view=switch_view)

    @app_commands.command(name=_T('battlepass'), description=_T('View your battlepass current tier'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def battlepass(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        riot_acc = await self.get_riot_account(user_id=interaction.user.id)

        switch_view = SwitchAccountView(interaction, riot_acc, self.get_battlepass)
        embeds = await self.get_battlepass(riot_acc[0], self.locale_converter(interaction.locale))

        await interaction.followup.send(embeds=embeds, view=switch_view)

    @app_commands.command(name=_T('point'), description=_T('View your remaining Valorant and Riot Points (VP/RP)'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.guild_only()
    async def point(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        get_riot_acc = await self.get_riot_account(user_id=interaction.user.id)

        switch_view = SwitchAccountView(interaction, get_riot_acc, self.get_point)
        embeds = await self.get_point(get_riot_acc[0], self.locale_converter(interaction.locale))

        await interaction.followup.send(embeds=embeds, view=switch_view)

    @app_commands.command(name=_T('bundle'), description='inspect a specific bundle')
    @app_commands.describe(maybe_uuid="The name of the bundle you want to inspect!")
    @app_commands.rename(maybe_uuid=_T('bundle'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def bundle(self, interaction: Interaction, maybe_uuid: str) -> None:

        await interaction.response.defer()

        locale = self.locale_converter(interaction.locale)

        bundle = self.v_client.get_bundle(maybe_uuid)

        if bundle is not None:

            embeds = []

            embed = Embed(
                description=f"Featured Bundle: {bold(f'{bundle.name_localizations.from_locale_code(locale)} Collection')}\n"  # noqa: E501
                f"{PointEmoji.valorant_point} {bundle.price}",
                colour=self.bot.theme.purple,
            )
            if bundle.display_icon_2 is not None:
                embed.set_image(url=bundle.display_icon_2)

            embeds.append(embed)

            for item in sorted(bundle.items, key=lambda i: i.price, reverse=True):
                emoji = ContentTierEmoji.from_name(item.rarity.dev_name) if isinstance(item, Skin) else ''
                e = Embed(
                    title=f"{emoji} {bold(item.name_localizations.from_locale_code(locale))}",
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

            await interaction.followup.send(f"Could not find bundle with name {bold(maybe_uuid)}")

    @app_commands.command(name=_T('bundles'), description=_T('Show the current featured bundles'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.guild_only()
    async def bundles(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        locale = self.locale_converter(interaction.locale)

        bundles = await self.get_featured_bundle()

        select_view = FeaturedBundleView(interaction, bundles)

        all_embeds: Dict[str, List[discord.Embed]] = {}

        embeds_stuffs = []

        for bundle in bundles:

            # build embeds stuff
            s_embed = discord.Embed(title=bundle.name_localizations.from_locale_code(locale), description='')
            if bundle.description_extra is not None:
                s_embed.description += f'{italics(bundle.description_extra_localizations.from_locale_code(locale))}\n'
            s_embed.description += (
                f'{PointEmoji.valorant_point} {bold(str(bundle.discount_price))} - '
                f'expires {format_relative(bundle.expires_at)}'
            )

            if bundle.display_icon_2 is not None:
                s_embed.set_thumbnail(url=bundle.display_icon_2)

                color_thief = self.featured_bundle_color.get(bundle.uuid)
                if color_thief is None:
                    banner_url_read = await bundle.display_icon_2.read()
                    color_thief = ColorThief(io.BytesIO(banner_url_read)).get_color()
                    self.featured_bundle_color[bundle.uuid] = color_thief

                s_embed.colour = discord.Colour.from_rgb(*color_thief)

            embeds_stuffs.append(s_embed)

            # build embeds
            embeds = []
            embed = Embed(
                description=f"Featured Bundle: {bold(f'{bundle.name_localizations.from_locale_code(locale)} Collection')}\n"  # noqa: E501
                f"{PointEmoji.valorant_point} {bold(str(bundle.discount_price))} {strikethrough(str(bundle.price))} "
                f"{italics(f'(Expires {format_relative(bundle.expires_at)})')}",
                colour=self.bot.theme.purple,
            )
            if bundle.display_icon_2 is not None:
                embed.set_image(url=bundle.display_icon_2)

            embeds.append(embed)

            for item in sorted(bundle.items, key=lambda i: i.price, reverse=True):
                emoji = ContentTierEmoji.from_name(item.rarity.dev_name) if isinstance(item, Skin) else ''

                price_label = f"{PointEmoji.valorant_point} "

                item_price = item.price
                item_discounted_price = item.discounted_price

                if not isinstance(item, valorant.SkinBundle) or item.is_melee():
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

        # client = await self.valo_client(interaction.user.id)
        # contracts = client.http.contracts_fetch()

        await interaction.followup.send(...)

    @app_commands.command(name=_T('patchnote'), description=_T('Patch notes'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.guild_only()
    async def patchnote(self, interaction: Interaction) -> None:

        await interaction.response.defer()

        patch_note = await self.get_patch_notes(interaction.locale)

        color_thief = self.patch_note_color.get(patch_note.latest.uid)
        if color_thief is None:
            banner_url_read = await patch_note.latest.banner.read()
            color_thief = ColorThief(io.BytesIO(banner_url_read)).get_palette(color_count=5)
            self.patch_note_color[patch_note.latest.uid] = color_thief  # cache color_thief

        embed = discord.Embed(
            title=patch_note.latest.title,
            timestamp=patch_note.latest.timestamp.replace(tzinfo=timezone.utc),
            url=patch_note.latest.url,
            colour=discord.Colour.from_rgb(*(random.choice(color_thief))),
            description=patch_note.latest.description,
        )
        embed.set_image(url=patch_note.latest.banner)
        embed.set_footer(text=patch_note.latest.category_title)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label=patch_note.see_article_title, url=patch_note.latest.url, emoji='🔗'))

        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name=_T('agent'), description=_T('View agent info'))
    @app_commands.guild_only()
    @app_commands.rename(maybe_uuid='agent')
    @dynamic_cooldown(cooldown_5s)
    async def agent(self, interaction: Interaction, maybe_uuid: str = None) -> None:

        # หน้าเลือก agent role ทำเหมือนน้อง nextcord

        await interaction.response.defer()

        locale = self.locale_converter(interaction.locale)

        agent = self.v_client.get_agent(maybe_uuid)

        if agent is not None:

            embed = Embed(
                title=agent.display_name,
                description=italics(agent.description_localizations.from_locale_code(locale)),
                colour=int(random.choice(agent.background_gradient_colors)[:-2], 16),
            )
            embed.set_image(url=agent.full_portrait)
            embed.set_thumbnail(url=agent.display_icon)
            embed.set_footer(
                text=agent.role.name_localizations.from_locale_code(locale), icon_url=agent.role.display_icon
            )

            # TODO: add agent abilities

            buttons = (
                ui.Button(label="Full Portrait", url=agent.full_portrait.url),
                ui.Button(label="Display Icon", url=agent.display_icon.url),
                ui.Button(label="Background", url=agent.background),
            )
            view = BaseView()
            for button in buttons:
                view.add_item(button)

            await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name=_T('agents'), description=_T('Agent Contracts'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def agents(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        riot_acc = await self.get_riot_account(user_id=interaction.user.id)

        await self.v_client.set_authorize(riot_acc[0])

        contracts = await self.v_client.fetch_contracts()

        agent_contract = contracts.special_contract()

        if agent_contract is None:
            return await interaction.followup.send("No active agent contract")

        print(agent_contract)

    @app_commands.command(name=_T('buddy'), description=_T('View buddy info'))
    @app_commands.guild_only()
    @app_commands.rename(maybe_uuid='buddy')
    @dynamic_cooldown(cooldown_5s)
    async def buddy(self, interaction: Interaction, maybe_uuid: str = None) -> None:

        await interaction.response.defer()

        locale = self.locale_converter(interaction.locale)
        buddy = self.v_client.get_buddy_level(maybe_uuid)

        if buddy is not None:
            embed = Embed(colour=self.bot.theme.purple)

            if isinstance(buddy, Buddy):
                embed.set_author(
                    name=buddy.name_localizations.from_locale_code(locale),
                    icon_url=buddy.theme.display_icon if buddy.theme is not None else None,
                    url=buddy.display_icon,
                )

            elif isinstance(buddy, BuddyLevel):
                embed.set_author(
                    name=buddy.base_buddy.name_localizations.from_locale_code(locale),
                    url=buddy.display_icon,
                    icon_url=buddy.base_buddy.theme.display_icon if buddy.base_buddy.theme is not None else None,
                )
            embed.set_image(url=buddy.display_icon)

            view = BaseView()
            view.add_item(ui.Button(label="Display Icon", url=buddy.display_icon.url))

            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send("No buddy found")

    @app_commands.command(name=_T('spray'), description=_T('View spray info'))
    @app_commands.guild_only()
    @app_commands.rename(maybe_uuid='spray')
    @dynamic_cooldown(cooldown_5s)
    async def spray(self, interaction: Interaction, maybe_uuid: str = None) -> None:

        await interaction.response.defer()

        locale = self.locale_converter(interaction.locale)
        spray = self.v_client.get_spray(maybe_uuid)

        if spray is not None:
            embed = Embed(colour=self.bot.theme.purple)  # TODO: get color from spray
            view = BaseView()

            if isinstance(spray, Spray):
                embed.set_author(
                    name=spray.name_localizations.from_locale_code(locale),
                    url=spray.display_icon,
                    icon_url=spray.theme.display_icon if spray.theme is not None else None,
                )
                embed.set_image(url=spray.animation_gif or spray.full_transparent_icon or spray.display_icon)
                if spray.animation_gif:
                    view.add_item(ui.Button(label="Animation Gif", url=spray.animation_gif.url))
                if spray.full_transparent_icon:
                    view.add_item(ui.Button(label="Full Transparent Icon", url=spray.full_transparent_icon.url))
                if spray.display_icon:
                    view.add_item(ui.Button(label="Display Icon", url=spray.display_icon.url))

            elif isinstance(spray, SprayLevel):
                base_spray = spray.base_spray
                embed.set_author(
                    name=base_spray.name_localizations.from_locale_code(locale),
                    icon_url=base_spray.theme.display_icon if base_spray.theme is not None else None,
                    url=spray.display_icon,
                )
                embed.set_image(
                    url=base_spray.animation_gif
                    or base_spray.full_transparent_icon
                    or base_spray.display_icon
                    or spray.display_icon
                )

                if base_spray.animation_gif:
                    view.add_item(ui.Button(label="Animation Gif", url=base_spray.animation_gif.url))
                if base_spray.full_transparent_icon:
                    view.add_item(ui.Button(label="Full Transparent Icon", url=base_spray.full_transparent_icon.url))
                if base_spray.display_icon:
                    view.add_item(ui.Button(label="Display Icon", url=base_spray.display_icon.url))

            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send("No spray found")

    player = app_commands.Group(name=_T('player'), description=_T('Player commands'), guild_only=True)

    @player.command(name=_T('card'), description=_T('View player card'))
    @dynamic_cooldown(cooldown_5s)
    @app_commands.rename(maybe_uuid='card')
    async def player_card(self, interaction: Interaction, maybe_uuid: str):

        await interaction.response.defer()

        locale = self.locale_converter(interaction.locale)
        player_card = self.v_client.get_player_card(maybe_uuid)

        if player_card is not None:
            embed = Embed(colour=self.bot.theme.purple)
            embed.set_author(
                name=player_card.name_localizations.from_locale_code(locale),
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
    @app_commands.rename(maybe_uuid='title')
    async def player_title(self, interaction: Interaction, maybe_uuid: str):

        await interaction.response.defer()

        locale = self.locale_converter(interaction.locale)
        player_title = self.v_client.get_player_title(maybe_uuid)

        if player_title is not None:
            embed = Embed(colour=self.bot.theme.purple)

    @app_commands.command(name=_T('weapon'), description=_T('View weapon info'))
    @app_commands.guild_only()
    @app_commands.rename(maybe_uuid='weapon')
    @dynamic_cooldown(cooldown_5s)
    async def weapon(self, interaction: Interaction, maybe_uuid: str = None) -> None:
        ...

    @app_commands.command(name=_T('skin'), description=_T('View skin info'))
    @app_commands.guild_only()
    @app_commands.rename(maybe_uuid='skin')
    @dynamic_cooldown(cooldown_5s)
    async def skin(self, interaction: Interaction, maybe_uuid: str = None) -> None:
        ...

    # auto complete
    @bundle.autocomplete('maybe_uuid')
    @agent.autocomplete('maybe_uuid')
    @buddy.autocomplete('maybe_uuid')
    @spray.autocomplete('maybe_uuid')
    @weapon.autocomplete('maybe_uuid')
    @skin.autocomplete('maybe_uuid')
    @player_card.autocomplete('maybe_uuid')
    @player_title.autocomplete('maybe_uuid')
    async def get_all_auto_complete(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:

        locale = self.locale_converter(interaction.locale)

        results: List[app_commands.Choice[str]] = []
        mex_index = 25

        command = interaction.command

        if command is self.bundle:
            bundle_list = self.get_all_bundles()
            namespace = interaction.namespace.bundle
            mex_index = 15

            for bundle in sorted(bundle_list, key=lambda a: a.name_localizations.from_locale_code(locale)):
                if bundle.name_localizations.from_locale_code(locale).lower().startswith(namespace.lower()):

                    bundle_name = bundle.name_localizations.from_locale_code(locale)

                    index = 2
                    for choice in results:
                        if choice.name.startswith(bundle_name):
                            bundle_name = f"{bundle_name} {index}"
                            index += 1

                    results.append(app_commands.Choice(name=bundle_name, value=bundle.uuid))
                    if len(results) >= mex_index:
                        break

        elif command in [
            self.agent,
            self.buddy,
            self.spray,
            self.weapon,
            self.skin,
            self.player_card,
            self.player_title,
        ]:

            if command is self.agent:
                value_list = self.get_all_agents()
                namespace = interaction.namespace.agent
            elif command is self.buddy:
                value_list = self.get_all_buddies()
                namespace = interaction.namespace.buddy
            elif command is self.spray:
                value_list = self.get_all_sprays()
                namespace = interaction.namespace.spray
            elif command is self.weapon:
                value_list = self.get_all_weapons()
                namespace = interaction.namespace.weapon
            elif command is self.skin:
                value_list = self.get_all_skins()
                namespace = interaction.namespace.skin
            elif command is self.player_card:
                value_list = self.get_all_player_cards()
                namespace = interaction.namespace.card
            elif command is self.player_title:
                value_list = self.get_all_player_titles()
                namespace = interaction.namespace.title
            else:
                return []

            for value in sorted(value_list, key=lambda a: a.name_localizations.from_locale_code(locale)):
                if value.name_localizations.from_locale_code(locale).lower().startswith(namespace.lower()):

                    value_name = value.name_localizations.from_locale_code(locale)

                    if value_name == ' ':
                        continue

                    if not value_name.startswith('.') and not namespace.startswith('.'):
                        results.append(app_commands.Choice(name=value_name, value=value.uuid))
                    elif namespace.startswith('.'):
                        results.append(app_commands.Choice(name=value_name, value=value.uuid))

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
    #     ...

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
    #     ...

    # @app_commands.command(name=_T('leaderboard'), description=_T('Shows your Region Leaderboard'))
    # @app_commands.describe(region='Select region to get the leaderboard')
    # @dynamic_cooldown(cooldown_5s)
    # @app_commands.guild_only()
    # async def leaderboard(self, interaction: Interaction, region: Literal['AP', 'EU', 'NA', 'KR']) -> None:
    #     ...

    # @app_commands.command(name=_T('collection'), description=_T('Shows your collection'))
    # @dynamic_cooldown(cooldown_5s)
    # @app_commands.guild_only()
    # async def collection(self, interaction: Interaction) -> None:
    #
    #     await interaction.response.defer()
    #
    #     riot_acc = await self.get_riot_account(user_id=interaction.user.id)
    #     client = await self.v_client.run(auth=riot_acc)
    #     loadout = await client.fetch_player_loadout()
    #
    #     file = await player_collection(loadout)
    #
    #     embed = Embed(color=self.bot.theme.primacy)
    #     embed.set_image(url="attachment://collection.png")
    #
    #     await interaction.followup.send(embed=embed, file=file)
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

    # @app_commands.command(name=_T('cookies'), description=_T('Log in with your Riot acoount by Cookies'))
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
