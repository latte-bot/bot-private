from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional, Union

import discord
import valorant
from async_lru import alru_cache
from discord import Interaction, TextStyle, ui

from utils.views import ViewAuthor

from ._enums import ValorantLocale

if TYPE_CHECKING:
    from valorant import Client as ValorantClient
    from valorant.models import NightMarket

    from .valorant import RiotAuth


# - multi-factor modal


class RiotMultiFactorModal(ui.Modal, title='Two-factor authentication'):
    """Modal for riot login with multifactorial authentication"""

    def __init__(self, try_auth: RiotAuth) -> None:
        super().__init__(timeout=120, custom_id='wait_for_modal')
        self.try_auth = try_auth
        self.code: Optional[str] = None
        self.interaction: Optional[Interaction] = None
        self.two2fa = ui.TextInput(
            label='Input 2FA Code',
            placeholder='2FA Code',
            max_length=6,
            # min_length=6,
            style=TextStyle.short,
            custom_id=self.custom_id + '_2fa',
        )
        self.add_item(self.two2fa)

    async def on_submit(self, interaction: Interaction) -> None:
        code = self.two2fa.value

        if not code:
            await interaction.response.send_message('Please input 2FA code', ephemeral=True)
            return

        if not code.isdigit():
            await interaction.response.send_message('Invalid code', ephemeral=True)
            return

        self.code = code
        self.interaction = interaction
        self.stop()

    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        # TODO: supress error
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)

        # Make sure we know what the error actually is
        traceback.print_tb(error.__traceback__)


# - switch account view


class SwitchAccountView(ViewAuthor):
    """View for switching account"""

    def __init__(
        self,
        interaction: Interaction,
        riot_acc: List[RiotAuth],
        func: Callable[[RiotAuth, Union[str, ValorantLocale]], Awaitable[List[discord.Embed]]],
        *,
        timeout: Optional[float] = 600,
    ) -> None:
        self.interaction: Interaction = interaction
        self.riot_acc: List[RiotAuth] = riot_acc
        self.func = func
        super().__init__(interaction, timeout=timeout)
        self.build_buttons()
        self.max_size = len(self.riot_acc)

    @staticmethod
    def locale_converter(locale: discord.Locale) -> str:
        return ValorantLocale.from_discord(str(locale))

    def build_buttons(self) -> None:
        for index, acc in enumerate(self.riot_acc, start=1):
            self.add_item(
                ButtonAccountSwitch(
                    label='Account #' + str(index),
                    custom_id=acc.puuid,
                    other_view=self,
                    disabled=True if index == 1 else False,
                )
            )

    # alias for func + alru_cache
    # @alru_cache(maxsize=5)
    async def get_embeds(self, riot_acc: RiotAuth, locale: Union[str, ValorantLocale]) -> List[discord.Embed]:
        return await self.func(riot_acc, locale)

    async def on_timeout(self) -> None:

        # cache clear
        # self.get_embeds.cache_clear()

        original_response = await self.interaction.original_response()
        if original_response:
            for item in self.children:
                if isinstance(item, ui.Button):
                    item.disabled = True
            await original_response.edit(view=self)

    async def on_error(self, interaction: Interaction, error: Exception, item: ui.Item[Any]) -> None:

        self.interaction.client.dispatch('riot_account_error', interaction.user.id)

        return await super().on_error(interaction, error, item)


class ButtonAccountSwitch(ui.Button['SwitchAccountView']):
    def __init__(self, label: str, custom_id: str, other_view: SwitchAccountView, **kwargs) -> None:
        self.other_view = other_view
        super().__init__(label=label, custom_id=custom_id, style=discord.ButtonStyle.gray, **kwargs)

    async def callback(self, interaction: Interaction) -> None:
        assert self.other_view is not None

        await interaction.response.defer()

        # enable all buttons without self
        self.disabled = True
        for item in self.other_view.children:
            if isinstance(item, ui.Button):
                if item.custom_id != self.custom_id:
                    item.disabled = False

        for acc in self.other_view.riot_acc:
            if acc.puuid == self.custom_id:
                locale = self.other_view.locale_converter(interaction.locale)

                import time
                start_time = time.time()

                embeds = await self.other_view.get_embeds(acc, locale)

                print(f'--- {time.time() - start_time} seconds ---')
                await interaction.edit_original_response(embeds=embeds, view=self.other_view)
                break


# - bundle view


class FeaturedBundleView(ViewAuthor):
    def __init__(self, interaction: Interaction, bundles: List[valorant.Bundle]) -> None:
        self.interaction = interaction
        self.bundles = bundles
        self.locale = ValorantLocale.from_discord(str(interaction.locale))
        self.all_embeds: Dict[str, List[discord.Embed]] = {}
        super().__init__(interaction, timeout=600)
        self.build_buttons(bundles)

    def build_buttons(self, bundles: List[valorant.Bundle]) -> None:
        for index, bundle in enumerate(bundles, start=1):
            self.add_item(
                FeaturedBundleButton(
                    other_view=self,
                    label=bundle.name_localizations.from_locale_code(self.locale),
                    custom_id=bundle.uuid,
                    style=discord.ButtonStyle.blurple,
                )
            )

    async def on_timeout(self) -> None:
        original_response = await self.interaction.original_response()
        if original_response:
            for item in self.children:
                if isinstance(item, ui.Button):
                    item.disabled = True
            await original_response.edit(view=self)


class FeaturedBundleButton(ui.Button['FeaturedBundleView']):
    def __init__(self, other_view: FeaturedBundleView, **kwargs) -> None:
        self.other_view = other_view
        super().__init__(**kwargs)

    async def callback(self, interaction: Interaction) -> None:
        assert self.other_view is not None

        await interaction.response.edit_message(embeds=self.other_view.all_embeds[self.custom_id], view=None)


# nightmarket view


class NightMarketView(ViewAuthor):
    def __init__(self, interaction: Interaction, valo_client: ValorantClient, night_market: NightMarket) -> None:
        self.interaction = interaction
        self.valo_client = valo_client
        self.night_market = night_market
        super().__init__(interaction, timeout=120)
        self._fill_skins()

    def _fill_skins(self) -> None:
        ...

    async def start(self) -> None:
        ...
