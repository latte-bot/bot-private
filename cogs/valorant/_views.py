from __future__ import annotations

import datetime
import random
import traceback
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import discord
import valorantx
from async_lru import alru_cache
from discord import ButtonStyle, Interaction, TextStyle, ui
from valorantx import CurrencyType, MissionType

from utils.chat_formatting import bold, strikethrough
from utils.errors import CommandError
from utils.formats import format_relative
from utils.i18n import _
from utils.views import ViewAuthor

from ._database import ValorantUser
from ._embeds import Embed, MatchEmbed
from ._enums import PointEmoji, ResultColor, ValorantLocale

if TYPE_CHECKING:
    from valorantx import Collection, NightMarket, SkinCollection, SprayCollection

    from bot import LatteBot

    from ._client import Client as ValorantClient
    from .valorant import RiotAuth


# TODO: view cooldown

# - multi-factor modal


class RiotMultiFactorModal(ui.Modal, title=_('Two-factor authentication')):
    """Modal for riot login with multifactorial authentication"""

    def __init__(self, try_auth: RiotAuth) -> None:
        super().__init__(timeout=120, custom_id='wait_for_modal')
        self.try_auth: RiotAuth = try_auth
        self.code: Optional[str] = None
        self.interaction: Optional[Interaction] = None
        self.two2fa = ui.TextInput(
            label=_('Input 2FA Code'),
            max_length=6,
            # min_length=6,
            style=TextStyle.short,
            custom_id=self.custom_id + '_2fa',
            placeholder=(
                _('You have 2FA enabled!')
                if self.try_auth.multi_factor_email is None
                else _('Riot sent a code to ') + self.try_auth.multi_factor_email
            ),
        )

        self.add_item(self.two2fa)

    async def on_submit(self, interaction: Interaction) -> None:
        code = self.two2fa.value

        if not code:
            await interaction.response.send_message(_('Please input 2FA code'), ephemeral=True)
            return

        if not code.isdigit():
            await interaction.response.send_message(_('Invalid code'), ephemeral=True)
            return

        self.code = code
        self.interaction = interaction
        self.stop()

    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        # TODO: supress error
        await interaction.response.send_message(_('Oops! Something went wrong.'), ephemeral=True)
        # Make sure we know what the error actually is
        traceback.print_tb(error.__traceback__)


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
                    label=str(index) + '. ' + bundle.name_localizations.from_locale(str(self.locale)),
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
    def __init__(self, other_view: FeaturedBundleView, **kwargs: Any) -> None:
        self.other_view = other_view
        super().__init__(**kwargs)

    async def callback(self, interaction: Interaction) -> None:
        assert self.other_view is not None
        self.other_view.selected = True
        # TODO: all_embeds get embeds
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

        self.add_option(
            label="Match's", value="match's", description=_("Match History!"), emoji='<:newmember:973160072425377823>'
        )
        self.add_option(
            label='Agents', value='agents', description=_("Top Agents!"), emoji='<:jetthappy:973158900679442432>'
        )
        self.add_option(label='Maps', value='maps', description=_("Top Maps!"), emoji='🗺️')
        self.add_option(label='Weapons', value='weapons', description=_("Top Weapons!"), emoji='🔫')
        self.add_option(
            label='Accuracy', value='accuracy', description=_("Your Accuracy!"), emoji='<:accuracy:973252558925742160>'
        )

    async def callback(self, interaction: Interaction) -> Any:
        assert self.view is not None
        await interaction.response.defer()
        await interaction.edit_original_response(content="Loading...")

        # value = self.values[0]
        #
        # if value == '__overview':
        #     await interaction.response.edit_message(embed=self.view.main_page, view=self.view)
        # elif value == 'matches':
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
    # self.stats['total_matches'] = len(match_history['History'])
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


class ButtonAccountSwitchX(ui.Button['SwitchingViewX']):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(style=discord.ButtonStyle.gray, **kwargs)

    async def callback(self, interaction: Interaction) -> None:
        assert self.view is not None

        # self.view.bot.translator.set_locale(interaction.locale)
        self.view.locale = interaction.locale
        await interaction.response.defer()

        # enable all buttons without self
        self.disabled = True
        for item in self.view.children:
            if isinstance(item, ui.Button):
                if item.custom_id != self.custom_id:
                    item.disabled = False

        for riot_auth in self.view.riot_auth_list:
            if riot_auth.puuid == self.custom_id:
                await self.view.start_view(riot_auth)
                break


class SwitchingViewX(ViewAuthor):
    def __init__(
        self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient, row: int = 0, **kwargs: Any
    ) -> None:
        super().__init__(interaction, timeout=kwargs.get('timeout', 600.0), **kwargs)
        self.bot: Union[discord.Client, LatteBot] = interaction.client
        self.v_user = v_user
        self.v_client: ValorantClient = client
        self.riot_auth_list = v_user.get_riot_accounts()
        self.locale: discord.Locale = interaction.locale
        self._build_buttons(row)

    def _build_buttons(self, row: int = 0) -> None:
        for index, acc in enumerate(self.riot_auth_list, start=1):
            if index >= 4:
                row += 1
            self.add_item(
                ButtonAccountSwitchX(
                    label="Account #" + str(index) if acc.hide_display_name else acc.display_name,
                    custom_id=acc.puuid,
                    disabled=(index == 1),
                    row=row,
                )
            )

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        pass

    def disable_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True

    @staticmethod
    async def _edit_message(message: discord.InteractionMessage, **kwargs: Any) -> None:
        try:
            await message.edit(**kwargs)
        except (discord.HTTPException, discord.NotFound, discord.Forbidden):
            pass

    async def on_timeout(self) -> None:

        if self.message is None:
            original_response = await self.interaction.original_response()
            if original_response:
                self.disable_buttons()
                await self._edit_message(original_response, view=self)
        else:
            self.disable_buttons()
            await self._edit_message(self.message, view=self)


class StoreSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=0)

    @alru_cache(maxsize=5)
    async def get_embeds(self, riot_auth: RiotAuth) -> List[discord.Embed]:
        sf = await self.v_client.fetch_store_front(riot_auth)
        store = sf.get_store()

        embeds = [
            Embed(
                description=_("Daily store for {user}\n").format(user=bold(riot_auth.display_name))
                + f"Resets {format_relative(store.reset_at)}"
            )
        ]

        for skin in store.get_skins():
            e = Embed(
                title=f"{skin.rarity.emoji} {bold(skin.name_localizations.from_locale(str(self.locale)))}",  # type: ignore
                description=f"{PointEmoji.valorant} {skin.price}",
                colour=self.bot.theme.dark,  # type: ignore
            )
            if skin.display_icon is not None:
                e.url = skin.display_icon.url
                e.set_thumbnail(url=skin.display_icon)

            if skin.rarity is not None:
                e.colour = int(skin.rarity.highlight_color[0:6], 16)

            embeds.append(e)

        return embeds

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embeds = await self.get_embeds(riot_auth)
        if self.message is None:
            self.message = await self.interaction.followup.send(embeds=embeds, view=self)
            return
        await self.message.edit(embeds=embeds, view=self)


class NightMarketSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=0)

    @alru_cache(maxsize=5)
    async def get_embeds(self, riot_auth: RiotAuth) -> List[discord.Embed]:
        sf = await self.v_client.fetch_store_front(riot_auth)
        nightmarket = sf.get_nightmarket()

        if nightmarket is None:
            raise CommandError(f"{bold('Nightmarket')} is not available.")

        embeds = [
            Embed(
                description=f"NightMarket for {bold(riot_auth.display_name)}\n"
                f"Expires {format_relative(nightmarket.expire_at)}",
                colour=self.bot.theme.purple,
            )
        ]

        for skin in nightmarket.get_skins():
            e = Embed(
                title=f"{skin.rarity.emoji} {bold(skin.name_localizations.from_locale(str(locale)))}",  # type: ignore
                description=f"{PointEmoji.valorant} {bold(str(skin.discount_price))}\n"
                f"{PointEmoji.valorant}  {strikethrough(str(skin.price))} (-{skin.discount_percent}%)",
                colour=self.bot.theme.dark,
            )
            if skin.display_icon is not None:
                e.url = skin.display_icon.url
                e.set_thumbnail(url=skin.display_icon)

            if skin.rarity is not None:
                e.colour = int(skin.rarity.highlight_color[0:6], 16)

            embeds.append(e)

        return embeds

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embeds = await self.get_embeds(riot_auth)
        if self.message is None:
            self.message = await self.interaction.followup.send(embeds=embeds, view=self)
            return
        await self.message.edit(embeds=embeds, view=self)


class BattlePassSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=0)

    @alru_cache(maxsize=5)
    async def get_embeds(self, riot_auth: RiotAuth) -> List[discord.Embed]:
        contract = await self.v_client.fetch_contracts(riot_auth)

        btp = contract.get_latest_contract(relation_type=valorantx.RelationType.season)

        next_reward = btp.get_next_reward()

        embed = discord.Embed(title='Battlepass for {display_name}'.format(display_name=bold(riot_auth.display_name)))
        embed.set_footer(
            text='TIER {tier} | {battlepass}'.format(
                tier=btp.current_tier, battlepass=btp.name_localizations.from_locale(str(self.locale))
            )
        )
        # TODO: name_localizations useful method

        if next_reward is not None:
            embed.description = ('{next}: {item}'.format(next=bold('NEXT'), item=next_reward.display_name),)
            if next_reward.display_icon is not None:
                if isinstance(next_reward, valorantx.SkinLevel):
                    embed.set_image(url=next_reward.display_icon)
                elif isinstance(next_reward, valorantx.PlayerCard):
                    embed.set_image(url=next_reward.wide_icon)
                else:
                    embed.set_thumbnail(url=next_reward.display_icon)

        embed.colour = self.bot.theme.purple if btp.current_tier <= 50 else self.bot.theme.gold

        return [embed]

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embeds = await self.get_embeds(riot_auth)
        if self.message is None:
            self.message = await self.interaction.followup.send(embeds=embeds, view=self)
            return
        await self.message.edit(embeds=embeds, view=self)


class PointSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=0)

    @alru_cache(maxsize=5)
    async def get_embeds(self, riot_auth: RiotAuth) -> List[discord.Embed]:
        wallet = await self.v_client.fetch_wallet(riot_auth)

        vp = self.v_client.get_currency(uuid=str(CurrencyType.valorant))
        rad = self.v_client.get_currency(uuid=str(CurrencyType.radianite))

        vp_display_name = vp.name_localizations.from_locale(str(self.locale))

        embed = Embed(title=f"{riot_auth.display_name} Point:")
        embed.add_field(
            name=f"{(vp_display_name if vp_display_name != 'VP' else 'Valorant')}",
            value=f"{vp.emoji} {wallet.valorant_points}",  # type: ignore
        )
        embed.add_field(
            name=f'{rad.name_localizations.from_locale(str(self.locale)).removesuffix(" Points")}',
            value=f'{rad.emoji} {wallet.radiant_points}',  # type: ignore
        )

        return [embed]

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embeds = await self.get_embeds(riot_auth)
        if self.message is None:
            self.message = await self.interaction.followup.send(embeds=embeds, view=self)
            return
        await self.message.edit(embeds=embeds, view=self)


class MissionSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=0)

    @alru_cache(maxsize=5)
    async def get_embeds(self, riot_auth: RiotAuth) -> List[discord.Embed]:

        contracts = await self.v_client.fetch_contracts(riot_auth)

        daily = []
        weekly = []
        tutorial = []
        npe = []

        all_completed = True

        daily_format = '{0} | **+ {1.xp:,} XP**\n- **`{1.progress}/{1.target}`**'
        for mission in contracts.missions:
            title = mission.title_localizations.from_locale(str(self.locale))
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

        embed = Embed(title=f"{riot_auth.display_name} Mission:")
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

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embeds = await self.get_embeds(riot_auth)
        if self.message is None:
            self.message = await self.interaction.followup.send(embeds=embeds, view=self)
            return
        await self.message.edit(embeds=embeds, view=self)


class CollectionSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=1)
        self._collection: Optional[valorantx.Collection] = None
        self._spray_pages: Optional[List[discord.Embed]] = None
        self._skin_pages: Optional[List[List[discord.Embed]]] = None
        self.current_embeds: Optional[List[discord.Embed]] = None
        self._current_riot_auth: Optional[RiotAuth] = None

    @ui.button(label=_('Skin'), style=ButtonStyle.blurple)
    async def skin(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        embeds = self.get_skin_pages(self._current_riot_auth)
        view = SkinCollectionView(interaction, self, embeds)
        await view.start()

    @ui.button(label=_('Spray'), style=ButtonStyle.blurple)
    async def spray(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        embeds = await self.get_spray_pages(self._current_riot_auth)
        view = SprayCollectionView(interaction, self, embeds)
        await view.start()

    @alru_cache(maxsize=5)
    async def get_embeds(self, riot_auth: RiotAuth) -> List[discord.Embed]:
        collection = self._collection = await self.v_client.fetch_collection(riot_auth)

        # mmr
        mmr = await collection._client.fetch_mmr()
        latest_tier = mmr.get_last_rank_tier()

        # wallet
        wallet = await collection._client.fetch_wallet(riot_auth)
        vp = self.v_client.get_currency(uuid=str(CurrencyType.valorant))
        rad = self.v_client.get_currency(uuid=str(CurrencyType.radianite))

        # loadout
        player_title = collection.get_player_title()
        player_card = collection.get_player_card()
        account_level = collection.get_account_level()
        # level_border = collection.get_level_border()

        e = discord.Embed()
        e.description = '{vp_emoji} {wallet_vp} {rad_emoji} {wallet_rad}'.format(
            vp_emoji=vp.emoji,  # type: ignore
            wallet_vp=wallet.valorant_points,
            rad_emoji=rad.emoji,  # type: ignore
            wallet_rad=wallet.radiant_points,
        )

        e.set_author(
            name='{display_name} - Collection'.format(display_name=riot_auth.display_name),
            icon_url=latest_tier.large_icon if latest_tier is not None else None,
        )
        e.set_footer(text='Lv. {level}'.format(level=account_level))

        if player_title is not None:
            e.title = player_title.text_localizations.from_locale(str(self.locale))

        if player_card is not None:
            e.set_image(url=player_card.wide_icon)
            card_color_thief = await self.bot.get_or_fetch_color(player_card.uuid, player_card.wide_icon)
            e.colour = discord.Colour.from_rgb(*(random.choice(card_color_thief)))

        return [e]

    @alru_cache(maxsize=5)
    async def get_spray_pages(self, riot_auth: RiotAuth) -> List[discord.Embed]:
        embeds = []
        for spray in self._collection.get_sprays():
            spray_fav = ' ★' if spray.is_favorite() else ''
            embed = discord.Embed(description=bold(spray.display_name) + spray_fav)
            spray_icon = spray.animation_gif or spray.full_transparent_icon or spray.display_icon
            if spray_icon is not None:
                embed.set_thumbnail(url=spray_icon)
                spray_color_thief = await self.bot.get_or_fetch_color(spray.uuid, spray.display_icon)
                embed.colour = discord.Colour.from_rgb(*(random.choice(spray_color_thief)))
            embeds.append(embed)
        return embeds

    @lru_cache(maxsize=5)
    def get_skin_pages(self, riot_auth: RiotAuth) -> List[List[discord.Embed]]:

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

            if skin_ is None:
                return 0

            weapon = skin_.get_weapon()

            if weapon is None:
                return 0

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
            else:
                return 18

        for index, skin in enumerate(sorted(self._collection.get_skins(), key=sort_skins)):

            skin_fav = ' ★' if skin.is_favorite() else ''

            embed = discord.Embed(
                description=(skin.rarity.emoji if skin.rarity is not None else '')  # type: ignore
                + ' '
                + bold(
                    (
                        skin.display_name
                        if not isinstance(skin, valorantx.SkinChromaLoadout)
                        else (skin.get_skin().display_name if skin.get_skin() is not None else '')
                    )
                    + skin_fav
                ),
                colour=int(skin.rarity.highlight_color[0:6], 16) if skin.rarity is not None else self.bot.theme.dark,
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

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embeds = await self.get_embeds(riot_auth)
        self._current_riot_auth = riot_auth
        self.current_embeds = embeds
        if self.message is not None:
            await self.message.edit(embeds=embeds, view=self)
            return
        self.message = await self.interaction.followup.send(embeds=embeds, view=self)


class SkinCollectionView(ViewAuthor):
    def __init__(
        self,
        interaction: Interaction,
        other_view: CollectionSwitchX,
        pages: List[List[discord.Embed]],
    ) -> None:
        super().__init__(interaction, timeout=600)
        self.other_view: CollectionSwitchX = other_view
        self._pages = pages
        self._current_page: int = 0
        self._update_buttons()

    @ui.button(label='≪', custom_id='first_page')
    async def first_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, 0)

    @ui.button(label=_("Back"), style=discord.ButtonStyle.blurple, custom_id='back_page')
    async def back_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, -1)

    @ui.button(label=_("Next"), style=discord.ButtonStyle.blurple, custom_id='next_page')
    async def next_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, +1)

    @ui.button(label='≫', custom_id='last_page')
    async def last_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, len(self._pages) - 1)

    @ui.button(label=_('Home'), style=discord.ButtonStyle.blurple, custom_id='back', row=1)
    async def home_button(self, interaction: Interaction, button: ui.Button):
        self.other_view.reset_timeout()
        await interaction.response.defer()
        await self.other_view.message.edit(embeds=self.other_view.current_embeds, view=self.other_view)

    def _update_buttons(self) -> None:
        page = self._current_page
        total = len(self._pages) - 1
        self.next_page.disabled = page == total
        self.back_page.disabled = page == 0
        self.first_page.disabled = page == 0
        self.last_page.disabled = page == total

    async def show_page(self, interaction: Interaction, page_number: int) -> None:
        if page_number <= 1 and page_number != 0:
            page_number = self._current_page + page_number
        self._current_page = page_number
        self._update_buttons()
        embeds = self._pages[self._current_page]
        await interaction.response.edit_message(embeds=embeds, view=self)

    async def show_checked_page(self, interaction: Interaction, page_number: int):
        try:
            await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def start(self) -> None:
        await self.other_view.interaction.edit_original_response(embeds=self._pages[0], view=self)


class SprayCollectionView(ViewAuthor):
    def __init__(
        self,
        interaction: Interaction,
        other_view: CollectionSwitchX,
        pages: List[discord.Embed],
    ) -> None:
        super().__init__(interaction, timeout=600)
        self.other_view = other_view
        self._pages = pages

    @ui.button(label=_('Back'), style=discord.ButtonStyle.blurple, custom_id='back', row=0)
    async def back(self, interaction: Interaction, button: ui.Button):
        self.other_view.reset_timeout()
        await interaction.response.defer()
        await self.other_view.message.edit(embeds=self.other_view.current_embeds, view=self.other_view)

    async def start(self) -> None:
        await self.other_view.interaction.edit_original_response(embeds=self._pages, view=self)


class MatchDetailsView(ViewAuthor):
    def __init__(
        self,
        interaction: Interaction,
        other_view: Optional[discord.ui.View] = None,
    ) -> None:
        super().__init__(interaction, timeout=600)
        self.embeds_mobile: List[discord.Embed] = []
        self.embeds_desktop: List[discord.Embed] = []
        self.current_page = 0
        self.is_on_mobile = False
        self.pages: List[discord.Embed] = []
        self.other_view: Optional[Union[discord.ui.View, CarrierSwitchX]] = other_view
        if self.other_view is None:
            self.remove_item(self.back_to_home)

    @ui.button(label='≪', style=ButtonStyle.blurple, custom_id='back_page')
    async def back_page(self, interaction: Interaction, button: ui.Button) -> None:
        await self.show_checked_page(interaction, -1)

    @ui.button(label='≫', style=ButtonStyle.blurple, custom_id='next_page')
    async def next_page(self, interaction: Interaction, button: ui.Button) -> None:
        await self.show_checked_page(interaction, +1)

    @ui.button(emoji='📱', style=ButtonStyle.green, custom_id='mobile')
    async def toggle_ui(self, interaction: Interaction, button: ui.Button) -> None:
        if self.is_on_mobile:
            button.emoji = '🖥️'
            self.is_on_mobile = False
        else:
            button.emoji = '📱'
            self.is_on_mobile = True
        await self.show_page(interaction, 0)

    @ui.button(label=_("Home"), style=ButtonStyle.green, custom_id='home_button')
    async def back_to_home(self, interaction: Interaction, button: ui.Button) -> None:
        if self.other_view is not None:
            self.other_view.reset_timeout()
        await interaction.response.defer()
        await self.message.edit(embeds=self.other_view.current_embeds, view=self.other_view)

    async def on_timeout(self) -> None:
        if self.message is not None:
            await self.message.edit(embed=self.pages[0], view=self)

    def _update_pages(self):
        self.pages = self.embeds_desktop if not self.is_on_mobile else self.embeds_mobile

    def get_page(self, page_number: int) -> Union[discord.Embed, List[discord.Embed]]:
        """:class:`list`: The page at the given page number."""
        return self.pages[page_number]

    async def show_page(self, interaction: Interaction, page_number: 0) -> None:
        self._update_pages()
        if page_number != 0:
            self.current_page = self.current_page + page_number
        page = self.get_page(self.current_page)
        self._update_buttons()
        kwargs = self._get_kwargs_from_page(page)
        await interaction.response.edit_message(**kwargs)

    async def show_checked_page(self, interaction: Interaction, page_number: int):
        try:
            await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    def _get_kwargs_from_page(self, page: Union[discord.Embed, List[discord.Embed]]) -> Dict[str, Any]:
        embeds = [embed for embed in page] if isinstance(page, list) else [page]
        return {'embeds': embeds, 'view': self}

    def _update_buttons(self) -> None:
        page = self.current_page
        total = len(self.pages) - 1
        self.back_page.disabled = page == 0
        self.next_page.disabled = page == total

    async def start(self, match: valorantx.MatchDetails) -> None:
        embeds = MatchEmbed(match)
        self.embeds_mobile: List[discord.Embed] = embeds.get_mobile()
        self.embeds_desktop: List[discord.Embed] = embeds.get_desktop()
        self.current_page = 0
        self._update_pages()
        self._update_buttons()
        if self.interaction.response.is_done():
            self.message = await self.interaction.edit_original_response(embed=self.pages[0], view=self)
            return
        await self.interaction.response.edit_message(embed=self.pages[0], view=self)
        self.message = await self.interaction.original_response()


class SelectMatchHistory(ui.Select['CarrierSwitchX']):
    def __init__(self, match_details: List[valorantx.MatchDetails]) -> None:
        self.match_details = match_details
        super().__init__(placeholder=_("Select Match to see details"), max_values=1, min_values=1, row=1)
        self.__fill_options()

    def __fill_options(self) -> None:
        for index, match in enumerate(self.match_details):
            enemy_team = match.get_enemy_team()
            me_team = match.get_me_team()

            players = match.get_players()

            left_team_score = me_team.rounds_won if me_team is not None else 0
            right_team_score = enemy_team.rounds_won if enemy_team is not None else 0

            if match.game_mode == valorantx.GameModeType.deathmatch:
                if match.me.is_winner():
                    _2nd_place = (sorted(players, key=lambda p: p.kills, reverse=True)[1]) if len(players) > 1 else None
                    _1st_place = match.me
                else:
                    _2nd_place = match.me
                    _1st_place = (sorted(players, key=lambda p: p.kills, reverse=True)[0]) if len(players) > 0 else None

                left_team_score = (_1st_place.kills if match.me.is_winner() else _2nd_place.kills) if _1st_place else 0
                right_team_score = (_2nd_place.kills if match.me.is_winner() else _1st_place.kills) if _2nd_place else 0

            self.add_option(
                label='{won} - {lose}'.format(won=left_team_score, lose=right_team_score),
                value=str(match.id),
                description='{map} - {queue}'.format(map=match.map.display_name, queue=match.game_mode.display_name),
                emoji=match.me.agent.emoji,  # type: ignore
            )

    async def callback(self, interaction: Interaction) -> Any:
        assert self.view is not None
        value = self.values[0]
        source = self.view.match_source
        match = source.get(value)
        view = MatchDetailsView(interaction, self.view)
        await view.start(match)
        # current_page = self.view.current_page
        # show_page = (current_page * 3) + int(value)
        # match = source[int(show_page)][int(value)]


class CarrierSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=2)
        self.mmr: Optional[valorantx.MMR] = None
        self.locale = interaction.locale
        self.current_page: int = 0
        self.pages: List[List[discord.Embed]] = []
        self.pages_source: List[List[valorantx.MatchDetails]] = []
        self.match_source: Dict[str, valorantx.MatchDetails] = {}
        self._max_pages: int = 0
        self.re_build: bool = False
        self.current_embeds: List[discord.Embed] = []
        self._queue: Optional[str] = None
        # self._is_build_select: bool = True

    @ui.button(label='≪', style=ButtonStyle.blurple, row=0)
    async def first_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, 0)

    @ui.button(label=_("Back"), style=ButtonStyle.blurple, row=0)
    async def back_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, self.current_page - 1)

    @ui.button(label=_("Next"), style=ButtonStyle.blurple, row=0)
    async def next_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, self.current_page + 1)

    @ui.button(label='≫', style=ButtonStyle.blurple, row=0)
    async def last_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, self.get_max_pages() - 1)

    def default_page(self, match: valorantx.MatchDetails) -> discord.Embed:

        me = match.me
        tier = me.get_competitive_rank()

        enemy_team = match.get_enemy_team()
        me_team = match.get_me_team()

        left_team_score = me_team.rounds_won
        right_team_score = enemy_team.rounds_won

        result = _("VICTORY")

        embed = discord.Embed(
            # title=match.game_mode.emoji + ' ' + match.game_mode.display_name,  # type: ignore
            description="{tier}{kda} {kills}/{deaths}/{assists}".format(
                tier=((tier.emoji + ' ') if match.queue == valorantx.QueueType.competitive else ''),  # type: ignore
                kda=bold('KDA'),
                kills=me.kills,
                deaths=me.deaths,
                assists=me.assists,
            ),
            color=ResultColor.win,
            timestamp=match.started_at,
        )

        if match.game_mode == valorantx.GameModeType.deathmatch:
            players = match.get_players()

            if match.me.is_winner():
                _2nd_place = (sorted(players, key=lambda p: p.kills, reverse=True)[1]) if len(players) > 1 else None
                _1st_place = me
            else:
                _2nd_place = me
                _1st_place = (sorted(players, key=lambda p: p.kills, reverse=True)[0]) if len(players) > 0 else None

            left_team_score = (_1st_place.kills if match.me.is_winner() else _2nd_place.kills) if _1st_place else 0
            right_team_score = (_2nd_place.kills if match.me.is_winner() else _1st_place.kills) if _2nd_place else 0

            if match.me.is_winner():
                result = '1ST PLACE'
            else:
                players = sorted(match.get_players(), key=lambda p: p.kills, reverse=True)
                for index, player in enumerate(players, start=1):
                    player_before = players[index - 1]
                    player_after = players[index] if len(players) > index else None
                    if player == me:
                        if index == 2:
                            result = '2ND PLACE'
                        elif index == 3:
                            result = '3RD PLACE'
                        else:
                            result = '{}TH PLACE'.format(index)

                        if player_before is not None or player_after is not None:
                            if player_before.kills == player.kills:
                                result += ' (TIED)'
                            elif player_after.kills == player.kills:
                                result += ' (TIED)'

        elif not match.me.is_winner():
            embed.colour = ResultColor.lose
            result = _("DEFEAT")

        if match.team_blue is not None and match.team_red is not None:
            if match.team_blue.rounds_won == match.team_red.rounds_won:
                embed.colour = ResultColor.draw
                result = 'DRAW'

        embed.set_author(
            name=f'{result} {left_team_score} - {right_team_score}',
            icon_url=me.agent.display_icon,
        )

        if match.map.splash is not None:
            embed.set_thumbnail(url=match.map.splash)
        embed.set_footer(
            text=f"{match.game_mode.display_name} • {match.map.name_localizations.from_locale(str(self.locale))}",
            icon_url=match.game_mode.display_icon
            # icon_url=tier.large_icon if tier is not None and match.queue == valorantx.QueueType.competitive else None,
        )
        return embed

    @staticmethod
    def tier_embed(mmr: Optional[valorantx.MMR] = None) -> Optional[discord.Embed]:
        if mmr is None:
            return None
        competitive = mmr.get_latest_competitive_season()
        if competitive is not None:
            parent_season = competitive.season.parent
            e = discord.Embed(colour=int(competitive.tier.background_color[:-2], 16), timestamp=datetime.datetime.now())
            e.set_author(name=competitive.tier.display_name, icon_url=competitive.tier.large_icon)
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

    def __build_source(self, match_details: List[valorantx.MatchDetails], mmr: Optional[valorantx.MMR]) -> None:
        self.match_source = {match.id: match for match in match_details}
        self.__build_pages(match_details, mmr)
        self.__update_buttons()
        self._queue: Optional[str] = None
        self._max_pages: int = len(self.pages)
        if len(self.pages_source) > 0:
            self.__build_selects()

    def __build_pages(self, match_details: List[valorantx.MatchDetails], mmr: valorantx.MMR) -> None:

        self.pages = []
        self.pages_source = []

        source = []
        embeds = []

        tier_embed = self.tier_embed()

        for index, match in enumerate(match_details, start=1):
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
            elif index == len(match_details):
                if tier_embed is not None:
                    embeds.insert(0, tier_embed)
                self.pages_source.append(source)
                self.pages.append(embeds)

    def __build_selects(self, index: int = 0) -> None:
        source = self.pages_source[index]
        if not self.re_build:
            self.add_item(SelectMatchHistory(source))
            self.re_build = True
        else:
            for item in self.children:
                if isinstance(item, SelectMatchHistory):
                    self.remove_item(item)
                    self.add_item(SelectMatchHistory(source))

    def get_max_pages(self) -> int:
        """:class:`int`: The maximum number of pages required to paginate this sequence."""
        return self._max_pages

    def get_page(self, page_number: int) -> List[discord.Embed]:
        """:class:`list`: The page at the given page number."""
        return self.pages[page_number]

    def _get_kwargs_from_page(self, page: List[discord.Embed]) -> Dict[str, Any]:
        embeds = [embed for embed in page]  # TODO: why is this needed?
        self.current_embeds = embeds
        return {"embeds": embeds, "view": self}

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

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        self._queue = kwargs.pop('queue', self._queue)
        client = self.v_client.set_authorize(riot_auth)

        match_history = await client.fetch_match_history(queue=self._queue)
        match_details = match_history.get_match_details()
        mmr = await client.fetch_mmr()
        self.__build_source(match_details, mmr)

        self.current_embeds = embeds = self.pages[0]
        if self.message is None:
            self.message = await self.interaction.edit_original_response(embeds=embeds, view=self)
            return
        await self.message.edit(embeds=self.pages[0], view=self)


# match history views


class MatchDetailsSwitchX(MatchDetailsView):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction)
        self.v_user = v_user
        self.v_client: ValorantClient = client
        self.riot_auth_list = v_user.get_riot_accounts()
        self._build_buttons(row=1)
        self._queue: Optional[str] = None

    def _build_buttons(self, row: int = 0) -> None:
        for index, acc in enumerate(self.riot_auth_list, start=1):
            self.add_item(
                ButtonAccountSwitchX(
                    label="Account #" + str(index) if acc.hide_display_name else acc.display_name,
                    custom_id=acc.puuid,
                    disabled=(index == 1),
                    row=row,
                )
            )

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        self._queue = kwargs.pop('queue', self._queue)
        client = self.v_client.set_authorize(riot_auth)
        match_history = await client.fetch_match_history(queue=self._queue, start=0, end=1)

        if len(match_history.get_match_details()) == 0:
            self.disable_buttons()
            embed = discord.Embed(
                title="No matches found",
                description="You have no matches in your match history",
                color=discord.Color.red(),
            )
            if self.message is None:
                self.message = await self.interaction.edit_original_response(embed=embed, view=self)
            await self.message.edit(embed=embed, view=self)
            return
        self.current_page = 0
        await super().start(match=match_history.get_match_details()[0])

    def disable_buttons(self):
        self.back_page.disabled = self.next_page.disabled = self.toggle_ui.disabled = True

    def remove_button_account_switch(self) -> None:
        for item in self.children:
            if isinstance(item, ButtonAccountSwitchX):
                self.remove_item(item)

    def remove_all_items(self) -> None:
        for item in self.children:
            self.remove_item(item)

    async def on_timeout(self) -> None:
        self.remove_all_items()
        # TODO: partnership view
        await super().on_timeout()
