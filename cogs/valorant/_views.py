from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional, Union

import discord
import datetime
import valorantx
from discord import ButtonStyle, Interaction, TextStyle, ui

from utils.chat_formatting import bold
from utils.views import ViewAuthor

from ._embeds import MatchEmbed
from ._enums import ResultColor, ValorantLocale

if TYPE_CHECKING:
    from valorantx import Client as ValorantClient, Collection, NightMarket, SkinCollection, SprayCollection
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
        riot_auth: List[RiotAuth],
        func: Callable[[RiotAuth, Union[str, ValorantLocale]], Awaitable[List[discord.Embed]]],
        *,
        row: int = 0,
        timeout: Optional[float] = 600,
    ) -> None:
        self.interaction: Interaction = interaction
        self.riot_auth: List[RiotAuth] = riot_auth
        self.func = func
        super().__init__(interaction, timeout=timeout)
        self.build_buttons(row)
        self.max_size = len(self.riot_auth)

    @staticmethod
    def locale_converter(locale: discord.Locale) -> str:
        return ValorantLocale.from_discord(str(locale))

    def build_buttons(self, row: int = 0) -> None:
        for index, acc in enumerate(self.riot_auth, start=1):
            self.add_item(
                ButtonAccountSwitch(
                    label="Account #" + str(index) if acc.hide_display_name else acc.display_name,
                    custom_id=acc.puuid,
                    other_view=self,
                    disabled=(index == 1),
                    row=row,
                )
            )

    # @alru_cache(maxsize=5)
    async def get_embeds(self, riot_auth: RiotAuth, locale: Union[str, ValorantLocale]) -> List[discord.Embed]:
        return await self.func(riot_auth, locale)

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

        for acc in self.other_view.riot_auth:
            if acc.puuid == self.custom_id:
                locale = self.other_view.locale_converter(interaction.locale)
                embeds = await self.other_view.get_embeds(acc, locale)
                await interaction.edit_original_response(embeds=embeds, view=self.other_view)
                break


# - bundle view


class FeaturedBundleView(ViewAuthor):
    def __init__(self, interaction: Interaction, bundles: List[valorantx.Bundle]) -> None:
        self.interaction = interaction
        self.bundles = bundles
        self.locale = ValorantLocale.from_discord(str(interaction.locale))
        self.all_embeds: Dict[str, List[discord.Embed]] = {}
        super().__init__(interaction, timeout=600)
        self.build_buttons(bundles)
        self.selected: bool = False

    def build_buttons(self, bundles: List[valorantx.Bundle]) -> None:
        for index, bundle in enumerate(bundles, start=1):
            self.add_item(
                FeaturedBundleButton(
                    other_view=self,
                    label=bundle.name_localizations.from_locale(self.locale),
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
    def __init__(
        self,
        interaction: Interaction,
        valo_client: ValorantClient,
        night_market: NightMarket,
    ) -> None:
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
            label="Match's", value="match's", description=MATCH_HISTORY, emoji='<:newmember:973160072425377823>'
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


# match history views


class SelectMatchHistory(ui.Select['MatchHistoryView']):
    def __init__(self, match_details: List[valorantx.MatchDetails]) -> None:
        self.match_details = match_details
        super().__init__(placeholder="Select Match to see details", max_values=1, min_values=1, row=1)
        self.__fill_options()

    def __fill_options(self) -> None:
        for index, match in enumerate(self.match_details):
            enemy_team = match.get_enemy_team()
            my_team = match.get_me_team()

            rounds_won, rounds_lost = my_team.rounds_won, enemy_team.rounds_won

            self.add_option(
                label='{won} - {lose}'.format(won=rounds_won, lose=rounds_lost),
                value=str(match.id),
                description='{map} - {queue}'.format(map=match.map.display_name, queue=str(match.queue).capitalize()),
                # emoji=match.me.agent.emoji  # type: ignore,
            )

    async def callback(self, interaction: Interaction) -> Any:
        assert self.view is not None
        value = self.values[0]
        source = self.view.match_source
        match = source.get(value)
        view = MatchDetailsView(interaction, match)
        await view.start()
        # current_page = self.view.current_page
        # show_page = (current_page * 3) + int(value)
        # match = source[int(show_page)][int(value)]


class MatchPageSource:
    def __init__(self, pages: List[discord.Embed], source: List[valorantx.MatchDetails]) -> None:
        self.pages = pages
        self.source = source


class MatchHistoryView(ViewAuthor):
    def __init__(
        self,
        interaction: Interaction,
        match_details: List[valorantx.MatchDetails],
        mmr: Optional[valorantx.MMR],
        *arg: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(interaction, *arg, **kwargs)
        self.match_details: List[valorantx.MatchDetails] = match_details
        self.mmr = mmr
        self.other_view: Optional[MatchDetailsView] = kwargs.get("other_view", None)
        self.locale = ValorantLocale.from_discord(str(interaction.locale))
        self.current_page: int = 0
        self.pages: List[List[discord.Embed]] = []
        self.pages_source: List[List[valorantx.MatchDetails]] = []
        self.match_source: Dict[str, valorantx.MatchDetails] = {match.id: match for match in match_details}
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

    def default_page(self, match: valorantx.MatchDetails) -> discord.Embed:

        radiant_color = 0xFFFFAA
        immortal_color = 0xFD4554

        me = match.me
        tier = me.get_competitive_rank()

        TEXT_VICTORY = "VICTORY"
        TEXT_DEFEAT = "DEFEAT"
        TEXT_TIED = "TIED"
        TEXT_PLACE = "PLACE"
        TEXT_DRAW = "DRAW"

        enemy_team = match.get_enemy_team()
        my_team = match.get_me_team()

        if enemy_team.rounds_won != my_team.rounds_won:
            color = ResultColor.win if my_team.rounds_won > enemy_team.rounds_won else ResultColor.lose
            result = TEXT_VICTORY if my_team.rounds_won > enemy_team.rounds_won else TEXT_DEFEAT
        else:
            color = ResultColor.draw
            result = TEXT_TIED

        embed = discord.Embed(
            description=f"{tier.emoji} **KDA** {match.me.kills}/{match.me.deaths}/{match.me.assists}",  # type: ignore
            color=color,
            timestamp=match.started_at,
        )
        embed.set_author(
            name=f'{result} {my_team.rounds_won} - {enemy_team.rounds_won}',
            icon_url=match.me.agent.display_icon,
        )

        if match.map.splash is not None:
            embed.set_thumbnail(url=match.map.splash)
        embed.set_footer(
            text=f"{match.map.name_localizations.from_locale(self.locale)} • {str(match.queue).capitalize()}",
            icon_url=tier.large_icon if tier is not None and match.queue == valorantx.QueueID.competitive else None,
        )
        return embed

    def tier_embed(self) -> Optional[discord.Embed]:
        if self.mmr is None:
            return None
        competitive = self.mmr.get_latest_competitive_season()
        if competitive is not None:
            parent_season = competitive.season.parent
            e = discord.Embed(colour=int(competitive.tier.background_color[:-2], 16), timestamp=datetime.datetime.now())
            e.set_author(
                name=competitive.tier.display_name,
                icon_url=competitive.tier.large_icon)
            e.set_footer(
                text=str(competitive.ranked_rating)
                + '/100'
                + ' • '
                + parent_season.display_name
                + ' '
                + competitive.season.display_name
            )
            return e
        return None

    def __build_pages(self) -> None:

        source = []
        embeds = []

        tier_embed = self.tier_embed()

        for index, match in enumerate(self.match_details, start=1):
            embed = self.default_page(match)
            embeds.append(embed)
            source.append(match)

            if not index % 3:
                if tier_embed is not None:
                    embeds.insert(0, tier_embed)
                self.pages_source.append(source)
                self.pages.append(embeds)
                source = []
                embeds = []
            elif index == len(self.match_details):
                if tier_embed is not None:
                    embeds.insert(0, tier_embed)
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
        return {"embeds": embeds, "view": self}

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
                self.remove_item(item)
                self.add_item(SelectMatchHistory(source))

    async def start(self, interaction: Optional[Interaction] = None) -> None:

        interaction = interaction or self.interaction

        if len(self.pages) > 0:
            if interaction.response.is_done():
                return await interaction.followup.send(embeds=self.pages[0], view=self, ephemeral=True)
            await interaction.response.send_message(embeds=self.pages[0], view=self, ephemeral=True)
        else:
            await interaction.followup.send("No matches found", ephemeral=True)


class MatchDetailsView(ViewAuthor):
    def __init__(self, interaction: Interaction, match: valorantx.MatchDetails):
        super().__init__(interaction, timeout=180)
        embeds = MatchEmbed(match)
        self.embeds_mobile: List[discord.Embed] = embeds.get_desktop()
        self.embeds_desktop: List[discord.Embed] = embeds.get_desktop()
        self.current_page = 0
        self.is_on_mobile = False
        self.pages: List[discord.Embed] = []
        self.message: Optional[discord.Message] = None
        self.__update_pages()
        self.__fill_items()
        self.__update_buttons()

    @ui.button(label='≪', style=ButtonStyle.blurple, custom_id='back_page')
    async def back_page(self, interaction: Interaction, button: ui.Button) -> None:
        await self.show_page(interaction, -1)

    @ui.button(label='≫', style=ButtonStyle.blurple, custom_id='next_page')
    async def next_page(self, interaction: Interaction, button: ui.Button) -> None:
        await self.show_page(interaction, +1)

    @ui.button(emoji='📱', style=ButtonStyle.green, custom_id='mobile')
    async def toggle_ui(self, interaction: Interaction, button: ui.Button) -> None:
        if self.is_on_mobile:
            button.emoji = '🖥️'
            self.is_on_mobile = False
        else:
            button.emoji = '📱'
            self.is_on_mobile = True
        await self.show_page(interaction, 0)

    async def on_timeout(self) -> None:
        if self.message is not None:
            await self.message.edit(embed=self.pages[0], view=None)

    def __fill_items(self):
        self.clear_items()
        self.add_item(self.back_page)
        self.add_item(self.next_page)
        self.add_item(self.toggle_ui)

    def __update_pages(self):
        self.pages = self.embeds_desktop if not self.is_on_mobile else self.embeds_mobile

    def get_page(self, page_number: int) -> Union[discord.Embed, List[discord.Embed]]:
        """:class:`list`: The page at the given page number."""
        return self.pages[page_number]

    async def show_page(self, interaction: Interaction, page_number: 0) -> None:
        self.__update_pages()
        if page_number != 0:
            self.current_page = self.current_page + page_number
        page = self.get_page(self.current_page)
        self.__update_buttons()
        kwargs = self._get_kwargs_from_page(page)
        await interaction.response.edit_message(**kwargs)

    def _get_kwargs_from_page(self, page: Union[discord.Embed, List[discord.Embed]]) -> Dict[str, Any]:
        embeds = [embed for embed in page] if isinstance(page, list) else [page]
        return {'embeds': embeds, 'view': self}

    def __update_buttons(self) -> None:
        page = self.current_page
        total = len(self.pages) - 1
        self.back_page.disabled = page == 0
        self.next_page.disabled = page == total

    async def start(self):
        await self.interaction.response.edit_message(embed=self.pages[0], view=self)
        self.message = await self.interaction.original_response()


# collection views


class CollectionView(SwitchAccountView):
    def __init__(
        self,
        interaction: Interaction,
        riot_auth: List[RiotAuth],
        func: Callable[[RiotAuth, Union[str, ValorantLocale]], Awaitable[List[discord.Embed]]],
        spray_pages: List[discord.Embed],
        skin_pages: List[List[discord.Embed]],
    ):
        super().__init__(interaction, riot_auth, func, row=1, timeout=600)
        self._spray_pages = spray_pages
        self._skin_pages = skin_pages
        self.current_embeds: Optional[List[discord.Embed]] = None

    async def get_embeds(self, riot_auth: RiotAuth, locale: Union[str, ValorantLocale]) -> List[discord.Embed]:
        embeds, sprays, skins = await self.func(riot_auth, locale)
        self._spray_pages = sprays
        self._skin_pages = skins
        self.current_embeds = embeds
        return embeds

    def get_spray_pages(self):
        return self._spray_pages

    def get_skin_pages(self):
        return self._skin_pages

    @ui.button(label='Skin', style=ButtonStyle.blurple)
    async def skin(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        embeds = self.get_skin_pages()
        view = SkinCollectionView(interaction, self, embeds)
        await view.start()

    @ui.button(label='Spray', style=ButtonStyle.blurple)
    async def spray(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        embeds = self.get_spray_pages()
        view = SprayCollectionView(interaction, self, embeds)
        await view.start()

    async def start(self, embed: discord.Embed):
        await self.interaction.response.send_message(embed=embed, view=self)


class SkinCollectionView(ViewAuthor):
    def __init__(
        self,
        interaction: Interaction,
        other_view: CollectionView,
        pages: List[List[discord.Embed]],
    ) -> None:
        super().__init__(interaction, timeout=600)
        self.other_view = other_view
        self._pages = pages
        self._current_page: int = 0
        self._update_buttons()

    @ui.button(label='≪', custom_id='first_page')
    async def first_page(self, interaction: Interaction, button: ui.Button):
        await self.show_page(interaction, 0)

    @ui.button(label="Back", style=discord.ButtonStyle.blurple, custom_id='back_page')
    async def back_page(self, interaction: Interaction, button: ui.Button):
        await self.show_page(interaction, -1)

    @ui.button(label="Next", style=discord.ButtonStyle.blurple, custom_id='next_page')
    async def next_page(self, interaction: Interaction, button: ui.Button):
        await self.show_page(interaction, +1)

    @ui.button(label='≫', custom_id='last_page')
    async def last_page(self, interaction: Interaction, button: ui.Button):
        await self.show_page(interaction, len(self._pages) - 1)

    @ui.button(label='Back', style=discord.ButtonStyle.blurple, custom_id='back', row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(embeds=self.other_view.current_embeds, view=self.other_view)

    def _update_buttons(self) -> None:
        page = self._current_page
        total = len(self._pages) - 1
        self.next_page.disabled = page == total
        self.back_page.disabled = page == 0
        self.first_page.disabled = page == 0
        self.last_page.disabled = page == total

    async def show_page(self, interaction: Interaction, page_number: int) -> None:
        try:
            if page_number <= 1 and page_number != 0:
                page_number = self._current_page + page_number
            self._current_page = page_number
            self._update_buttons()
            embeds = self._pages[self._current_page]
            await interaction.response.edit_message(embeds=embeds, view=self)
        except (IndexError, ValueError):
            return

    async def start(self) -> None:
        await self.other_view.interaction.edit_original_response(embeds=self._pages[0], view=self)


class SprayCollectionView(ViewAuthor):
    def __init__(
        self,
        interaction: Interaction,
        other_view: CollectionView,
        pages: List[discord.Embed],
    ) -> None:
        super().__init__(interaction, timeout=600)
        self.other_view = other_view
        self._pages = pages

    @ui.button(label='Back', style=discord.ButtonStyle.blurple, custom_id='back', row=0)
    async def back(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(embeds=self.other_view.current_embeds, view=self.other_view)

    async def start(self) -> None:
        await self.other_view.interaction.edit_original_response(embeds=self._pages, view=self)
