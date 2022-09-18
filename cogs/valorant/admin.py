from __future__ import annotations

import os

import discord
from discord import Interaction, app_commands
from discord.app_commands import Choice, locale_str as _T

from ._abc import MixinMeta
from ._client import RiotAuth
from ._errors import NoAccountsLinked

SUPPORT_GUILD_ID = int(os.getenv('SUPPORT_GUILD_ID'))


class Admin(MixinMeta):

    cache = app_commands.Group(
        name=_T('cache'),
        description=_T('Cache commands'),
        default_permissions=discord.Permissions(administrator=True),
        guild_ids=[SUPPORT_GUILD_ID],
    )

    @cache.command(name=_T('clear'), description=_T('Clear cache'))
    @app_commands.choices(
        cache=[
            Choice(name=_T('All'), value='all'),
            Choice(name=_T('Bundle'), value='bundle'),
            Choice(name=_T('Featured Bundle'), value='featured_bundle'),
            Choice(name=_T('Locale'), value='locale'),
            Choice(name=_T('Patch Note'), value='patch_note'),
            Choice(name=_T('Riot Account'), value='riot_account'),
        ]
    )
    async def cache_clear(self, interaction: Interaction, cache: Choice[str]) -> None:

        if cache.value == 'bundle' or cache.value == 'all':
            self.get_all_bundles.cache_clear()  # type: ignore
        if cache.value == 'featured_bundle' or cache.value == 'all':
            self.get_featured_bundle.cache_clear()  # type: ignore
        if cache.value == 'locale' or cache.value == 'all':
            self.get_valorant_locale.cache_clear()  # type: ignore
        if cache.value == 'patch_note' or cache.value == 'all':
            self.get_patch_notes.cache_clear()  # type: ignore
        if cache.value == 'riot_account' or cache.value == 'all':
            self.get_riot_account.cache_clear()  # type: ignore

        if cache.value == 'all':
            msg = 'All cache has been cleared'
        else:
            msg = f'Cache `{cache.value}` has been cleared'

        await interaction.response.send_message(msg, ephemeral=True)

    asset = app_commands.Group(
        name=_T('asset'),
        description=_T('Asset commands'),
        default_permissions=discord.Permissions(administrator=True),
        guild_ids=[SUPPORT_GUILD_ID],
    )

    @asset.command(name=_T('fetch'), description=_T('Fetch asset'))
    async def asset_fetch(self, interaction: Interaction, with_price: bool, force: bool, reload: bool = True) -> None:

        await interaction.response.defer(ephemeral=True)

        try:
            riot_acc = await self.get_riot_account(user_id=self.bot.owner_id)
        except NoAccountsLinked:
            riot_acc = RiotAuth(self.bot.owner_id, bot=self.bot)
            await riot_acc.authorize(username=self.bot.riot_username, password=self.bot.riot_password)
        else:
            riot_acc = riot_acc[0]

        client = await self.v_client.set_authorize(riot_acc)
        await client.fetch_assets(with_price=with_price, reload=reload, force=force)

        await interaction.followup.send('Asset has been fetched', ephemeral=True)

    @asset.command(name=_T('clear'), description=_T('Clear asset'))
    @app_commands.choices(
        cache=[
            Choice(name=_T('All'), value='all'),
            Choice(name=_T('Assets'), value='assets'),
            Choice(name=_T('Offers'), value='offers'),
        ]
    )
    async def asset_clear(self, interaction: Interaction, cache: Choice[str]) -> None:
        if cache.value == 'assets':
            self.v_client.assets.clear_asset_cache()
        elif cache.value == 'offers':
            self.v_client.assets.clear_offer_cache()
        else:
            self.v_client.assets.clear_all_cache()

        msg = f'Cache `{cache.value}` has been cleared'
        await interaction.response.send_message(msg, ephemeral=True)

    @asset.command(name=_T('reload'), description=_T('Reload asset'))
    async def asset_reload(self, interaction: Interaction, with_price: bool = True) -> None:
        self.v_client.assets.reload_assets(with_price=with_price)
        await interaction.response.send_message('Asset has been reloaded', ephemeral=True)
