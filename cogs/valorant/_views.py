from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional, Union

import discord
import valorant
from async_lru import alru_cache
from discord import ButtonStyle, Interaction, TextStyle, ui

from utils.views import ViewAuthor

from ._enums import ResultColor, ValorantLocale

if TYPE_CHECKING:
    from valorant import Client as ValorantClient
    from valorant.models import NightMarket

    from .valorant import RiotAuth


# - multi-factor modal


class RiotMultiFactorModal(ui.Modal, title='Two-factor authentication'):
    """Modal for riot login with multifactorial authentication"""

    def __init__(self, try_auth: RiotAuth) -> None:
        super().__init__(timeout=120, custom_id='wait_for_modal')
        self.try_auth: RiotAuth = try_auth
        self.code: Optional[str] = None
        self.interaction: Optional[Interaction] = None
        self.two2fa = ui.TextInput(
            label='Input 2FA Code',
            max_length=6,
            # min_length=6,
            style=TextStyle.short,
            custom_id=self.custom_id + '_2fa',
        )
        if self.try_auth.multi_factor_email is not None:
            self.two2fa.placeholder = 'Riot sent a code to ' + self.try_auth.multi_factor_email
        else:
            self.two2fa.placeholder = 'You have 2FA enabled!'

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
        self.selected: bool = False

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
        if not self.selected:
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
        self.other_view.selected = True
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


# stats view


class StatsSelect(ui.Select['StatsView']):
    def __init__(self) -> None:
        super().__init__(placeholder="Select a stat", max_values=1, min_values=1, row=0)
        self.__fill_options()

    def __fill_options(self) -> None:
        self.add_option(label="Overview", value='__overview', emoji='🌟')

        MATCH_HISTORY = "Match History!"
        YOUR_ACCURASY = "Your Accuracy!"
        TOP_AGENTS = "Top Agents!"
        TOP_MAPS = "Top Maps!"
        TOP_WEAPONS = "Top Weapons!"

        self.add_option(
            label='Matchs', value='matchs', description=MATCH_HISTORY, emoji='<:newmember:973160072425377823>'
        )
        self.add_option(label='Agents', value='agents', description=TOP_AGENTS, emoji='<:jetthappy:973158900679442432>')
        self.add_option(label='Maps', value='maps', description=TOP_MAPS, emoji='🗺️')
        self.add_option(label='Weapons', value='weapons', description=TOP_WEAPONS, emoji='🔫')
        self.add_option(
            label='Accuracy', value='accuracy', description=YOUR_ACCURASY, emoji='<:accuracy:973252558925742160>'
        )

    async def callback(self, interaction: Interaction) -> Any:
        assert self.view is not None
        await interaction.response.defer()
        await interaction.edit_original_response(content="Loading...")

        # value = self.values[0]
        #
        # if value == '__overview':
        #     await interaction.response.edit_message(embed=self.view.main_page, view=self.view)
        # elif value == 'matchs':
        #     view = MatchHistoryView(
        #         historys=self.view.match_source,
        #         embeds=self.view.match_source_embed,
        #         other_view=self.view
        #     )
        #     await view.start(interaction)
        # # elif value == 'accuracy':
        #     # await interaction.response.send_message('Accuracy', ephemeral=True)
        # elif value == 'agents':
        #     view = AgentStatsView(
        #         stats=self.view.stats,
        #         other_view=self.view
        #     )
        #     await view.start(interaction)
        # elif value == 'maps':
        #     await interaction.response.send_message('Maps', ephemeral=True)
        # elif value == 'weapons':
        #     await interaction.response.send_message('Weapons', ephemeral=True)


class StatsView(ViewAuthor):
    def __init__(self, interaction: Interaction) -> None:
        self.interaction = interaction
        super().__init__(interaction, timeout=120)
        self.add_item(StatsSelect())

    # def default_page(self, author: bool = False, icon: bool = False) -> discord.Embed:
    #     embed = discord.Embed(title=self.player_title, color=self.color)
    #     if author:
    #         embed.set_author(name=self.name, icon_url=self.rank_icon)
    #     if icon:
    #         embed.set_image(url=self.icon)
    #     return embed
    #
    # def build_match_history(self, match_details: Dict):
    #     ...
    #
    # async def last_matches_competitive(self):
    #     ...
    # self.stats = self.stats
    # total_game = self.rank['current']['total_game']
    #
    # if total_game >= 25:
    #     total_game = 25
    #
    # match_history = self.endpoint.fetch_match_history(self.puuid, queue_id='competitive', start_index=0,
    #                                                   end_index=total_game)
    # self.stats['total_matchs'] = len(match_history['History'])
    #
    # for index, match in enumerate(match_history['History']):
    #     match_details = self.endpoint.fetch_match_details(match['MatchID'])
    #     better_match_details = self.build_match_history(match_details)
    #     if index == 0:
    #         self.get_playerItem(match_details)
    #         await self.pre_start()
    #
    #     self.fetch_player_stats(better_match_details)

    # def fetch_player_stats(self, data: Dict):
    #     ...
    #
    # def get_current_mmr(self):
    #     ...
    #
    # def get_player_item(self, match_details: Dict):
    #     ...

    # def static_embed(
    #         self, level: bool = True, title: bool = True, card: bool = True,
    #                  rank: bool = True) -> discord.Embed:
    #
    #     embed = discord.Embed()
    #     embed.set_author(name=self.name)
    #
    #     if level: embed.description = f"Level: {self.levels['level']}"
    #
    #     if title:
    #         if self.player_title is not None: embed.title = self.player_title['texts'][str(_locale)]
    #
    #     if card:
    #         if self.player_card is not None: embed.set_thumbnail(url=self.player_card['icon']['small'])
    #
    #     if rank:
    #         if self.rank_icon is not None: embed._author['icon_url'] = self.rank_icon
    #
    #     return embed

    # def pre_main_page(self) -> discord.Embed:
    #     loading_emoji = "<a:typing:597589448607399949>"
    #     embed = self.static_embed()
    #     embed.add_field(name='Rank', value=f"{self.rank_name.capitalize()}")
    #     embed.add_field(name='Headshot%', value=loading_emoji)
    #     embed.add_field(name='Score/Round', value=loading_emoji)
    #     embed.add_field(name='KDA Ratio', value=loading_emoji)
    #     embed.add_field(name='Win Ratio', value=loading_emoji)
    #     embed.add_field(name='Damage/Round', value=loading_emoji)
    #     embed.set_footer(text=f"{self.season}")
    #     return embed

    # def final_main_page(self) -> discord.Embed:
    #     ...

    async def pre_start(self):
        # pre_embed = self.pre_main_page()
        await self.interaction.followup.send("Loading...", view=self)

    # async def start(self) -> None:
    #     self.get_current_mmr()
    #     await self.last_matches_competitive()
    #
    #     self.final_page = self.final_main_page()
    #     await self.message.edit(embed=self.final_page, view=self)


# match history


class SelectMatchHistory(ui.Select['MatchHistoryView']):
    def __init__(self, match_details: List[valorant.MatchDetails]) -> None:
        self.match_details = match_details
        super().__init__(placeholder="Select Match to see details", max_values=1, min_values=1, row=1)
        self.__fill_options()

    def __fill_options(self) -> None:
        for index, match in enumerate(self.match_details):
            self.add_option(
                label=f'result score',
                value=str(index),
                description=f'{match.map.display_name} - {str(match.queue).capitalize()}'
                # emoji=agent_emoji
            )

    async def callback(self, interaction: Interaction) -> Any:
        assert self.view is not None
        value = self.values[0]
        source = self.view.match_embeds
        current_page = self.view.current_page

        show_page = (current_page * 3) + int(value)

        embeds, embeds_mobile = source[int(show_page)]
        view = MatchDetailsView(interaction, embeds, embeds_mobile)
        await view.start()


class MatchHistoryView(ViewAuthor):
    def __init__(
        self, interaction: Interaction, match_details: List[valorant.MatchDetails], *arg: Any, **kwargs: Any
    ) -> None:
        self.interaction: Interaction = interaction
        self.match_details: List[valorant.MatchDetails] = match_details
        self.other_view: Optional[MatchDetailsView] = kwargs.get('other_view', None)
        super().__init__(interaction, *arg, **kwargs)
        self.locale = ValorantLocale.from_discord(str(interaction.locale))
        self.current_page: int = 0
        self.pages_source: List[List[valorant.MatchDetails]] = []
        self.pages: List[List[discord.Embed]] = []
        self.message: Optional[discord.InteractionMessage] = None
        self.__build_pages()
        self.__update_buttons()
        self._max_pages: int = len(self.pages)
        if len(self.pages_source) > 0:
            self.__build_selects()

    @ui.button(label='≪', style=ButtonStyle.blurple)
    async def first_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, 0)

    @ui.button(label="Back", style=ButtonStyle.blurple)
    async def back_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, self.current_page - 1)

    @ui.button(label="Next", style=ButtonStyle.blurple)
    async def next_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, self.current_page + 1)

    @ui.button(label='≫', style=ButtonStyle.blurple)
    async def last_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, self.get_max_pages() - 1)

    def default_page(self, match: valorant.MatchDetails) -> discord.Embed:

        # radiant_color = 0xffffaa
        # immortal_color = 0xfd4554

        # TEXT_VICTORY = _("VICTORY")
        # TEXT_DEFEAT = _("DEFEAT")
        # TEXT_TIED = _("TIED")
        # TEXT_PLACE = _("PLACE")
        # TEXT_DRAW = _("DRAW")

        embed = discord.Embed(
            description=f"rank_emoji **KDA** {match.me.kills}/{match.me.deaths}/{match.me.assists}",
            # color=kwargs.get('color'),
            timestamp=match.started_at,
        )

        # TEXT_VICTORY = _("VICTORY")
        # TEXT_DEFEAT = _("DEFEAT")
        # TEXT_TIED = _("TIED")
        # TEXT_PLACE = _("PLACE")
        # TEXT_DRAW = _("DRAW")

        # score_info
        # match_score = f'{winner_score}:{loser_score}' if your_has_won else f'{loser_score}:{winner_score}'

        # if winner_score != loser_score:
        #     color = ResultColor.WIN if your_has_won else ResultColor.LOSE
        #     match_result = TEXT_VICTORY if your_has_won else TEXT_DEFEAT
        # else:
        #     color = ResultColor.DRAW
        #     match_result = TEXT_TIED

        embed.set_author(name="{match_result} {match_score}", icon_url=match.me.agent.display_icon)
        if match.map.splash is not None:
            embed.set_thumbnail(url=match.map.splash)
        embed.set_footer(
            text=f"{match.map.name_localizations.from_locale_code(self.locale)} • {str(match.queue).capitalize()}"
        )
        return embed

    def __build_pages(self) -> None:

        source = []
        embeds = []

        for index, match in enumerate(self.match_details, start=1):
            embed = self.default_page(match)
            embeds.append(embed)
            source.append(match)

            if not index % 3:
                self.pages_source.append(source)
                self.pages.append(embeds)
                source = []
                embeds = []
            elif index == len(self.match_details):
                self.pages_source.append(source)
                self.pages.append(embeds)

    def __build_selects(self, index: int = 0) -> None:
        source = self.pages_source[index]
        self.add_item(SelectMatchHistory(source))

    def get_max_pages(self) -> int:
        """:class:`int`: The maximum number of pages required to paginate this sequence."""
        return self._max_pages

    def get_page(self, page_number: int) -> List[discord.Embed]:
        """:class:`list`: The page at the given page number."""
        return self.pages[page_number]

    async def show_checked_page(self, interaction: Interaction, page_number: int):
        try:
            await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def show_page(self, interaction: Interaction, page_number: int) -> None:
        page = self.get_page(page_number)
        self.current_page = page_number
        self.__update_buttons()
        self.__update_select()
        kwargs = self._get_kwargs_from_page(page)
        await interaction.response.edit_message(**kwargs)

    def _get_kwargs_from_page(self, page: List[discord.Embed]) -> Dict[str, Any]:
        embeds = [embed for embed in page]
        return {'embeds': embeds, 'view': self}

    def __update_buttons(self) -> None:
        page = self.current_page
        total = len(self.pages) - 1
        self.next_page.disabled = page == total
        self.back_page.disabled = page == 0
        self.first_page.disabled = page == 0
        self.last_page.disabled = page == total

    def __update_select(self) -> None:
        source = self.pages_source[self.current_page]
        for item in self.children:
            if isinstance(item, ui.Select):
                print("update select")
                self.remove_item(item)
                self.add_item(SelectMatchHistory(source))

    async def start(self, interaction: Optional[Interaction] = None) -> None:

        interaction = interaction or self.interaction

        if len(self.pages) > 0:
            print("start", self.pages)
            if interaction.response.is_done():
                return await interaction.followup.send(embeds=self.pages[0], view=self, ephemeral=True)
            await interaction.response.send_message(embeds=self.pages[0], view=self, ephemeral=True)
        else:
            await interaction.followup.send("No matches found", ephemeral=True)


class MatchDetailsView(ViewAuthor):
    def __init__(
        self, interaction: Interaction, embeds_desktop: List[discord.Embed], embeds_mobile: List[discord.Embed]
    ):
        self.interaction = interaction
        self.embeds_desktop = embeds_desktop
        self.embeds_mobile = embeds_mobile
        super().__init__(interaction, timeout=180)
        self.current_page = 0
        self.is_on_mobile = False
        self.embeds: List[discord.Embed] = []
        self.message: Optional[discord.Message] = None
        self.__update_embed()
        self.__fill_items()
        self.__update_buttons()

    @ui.button(label='≪', style=ButtonStyle.blurple, custom_id='back_page')
    async def back_page(self, interaction: Interaction, button: ui.Button) -> None:
        await self.show_checked_page(interaction, -1)

    @ui.button(label='≫', style=ButtonStyle.blurple, custom_id='next_page')
    async def next_page(self, interaction: Interaction, button: ui.Button) -> None:
        await self.show_checked_page(interaction, +1)

    @ui.button(emoji='📱', style=ButtonStyle.green, custom_id='mobile')
    async def toggle_ui(self, interaction: Interaction, button: ui.Button) -> None:
        if button.custom_id == 'mobile':
            self.is_on_mobile = True
            self.toggle_ui.emoji = '🖥️'
            self.toggle_ui.custom_id = 'desktop'
            await interaction.response.edit_message(embed=self.embeds_mobile[self.current_page], view=self)
        else:
            self.is_on_mobile = False
            self.toggle_ui.emoji = '📱'
            self.toggle_ui.custom_id = 'mobile'
            await interaction.response.edit_message(embed=self.embeds_desktop[self.current_page], view=self)

    async def on_timeout(self) -> None:
        if self.message is not None:
            await self.message.edit(embed=self.embeds[0], view=None)

    def __fill_items(self):
        self.clear_items()
        self.add_item(self.back_page)
        self.add_item(self.next_page)
        self.add_item(self.toggle_ui)

    def __update_embed(self):
        self.embeds = self.embeds_desktop if not self.is_on_mobile else self.embeds_mobile

    # @ui.button(label='Share to friends', style=ButtonStyle.primary)
    # async def share_button(self, interaction: Interaction, button: ui.Button):
    #     self.remove_item(self.share_button)
    #     self.message = await interaction.channel.send(embed=self.current_embed, view=self)
    #     await interaction.response.edit_message(view=None, embed=None, content='\u200b')

    async def show_checked_page(self, interaction: Interaction, page_number: int):
        self.__update_embed()
        try:
            if page_number <= 1 and page_number != 0:
                page_number = self.current_page + page_number
            self.__update_buttons()
            await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def show_page(self, interaction: Interaction, page_number: int) -> None:
        self.current_page = page_number
        kwargs = self._get_kwargs_from_page()
        await interaction.response.edit_message(**kwargs)

    def _get_kwargs_from_page(self) -> Dict[str, Any]:
        embed = self.embeds[self.current_page]
        return {'embed': embed, 'view': self}

    def __update_buttons(self) -> None:
        page = self.current_page
        total = len(self.embeds) - 1
        self.back_page.disabled = page == 0
        self.next_page.disabled = page == total

    async def start(self):
        if self.interaction.response.is_done():
            self.message = await self.interaction.followup.send(embed=self.embeds[0], view=self)
            return
        await self.interaction.response.send_message(embed=self.embeds[0], view=self, ephemeral=True)
        self.message = await self.interaction.original_response()
