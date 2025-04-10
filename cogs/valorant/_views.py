from __future__ import annotations

import random
import traceback
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import discord
import valorantx
from async_lru import alru_cache
from discord import ButtonStyle, Interaction, TextStyle, ui

from utils.chat_formatting import bold
from utils.errors import CommandError
from utils.i18n import _
from utils.pages import LattePages, ListPageSource
from utils.views import ViewAuthor

from ._database import ValorantUser
from ._embeds import (
    MatchEmbed,
    game_pass_e,
    mission_e,
    nightmarket_e,
    skin_loadout_e,
    spray_loadout_e,
    store_e,
    wallet_e,
)
from ._enums import ResultColor, ValorantLocale

if TYPE_CHECKING:
    from valorantx import NightMarket
    from valorantx.models import contract

    from ._client import Client as ValorantClient, RiotAuth

# V = TypeVar('V', bound='View')
# - multi-factor modal

# TODO: from base Modal
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
        self.v_locale = ValorantLocale.from_discord(str(interaction.locale))
        self.all_embeds: Dict[str, List[discord.Embed]] = {}
        super().__init__(interaction, timeout=600)
        self.build_buttons(bundles)
        self.selected: bool = False

    def build_buttons(self, bundles: List[valorantx.Bundle]) -> None:
        for index, bundle in enumerate(bundles, start=1):
            self.add_item(
                FeaturedBundleButton(
                    other_view=self,
                    label=str(index) + '. ' + bundle.name_localizations.from_locale(str(self.v_locale)),
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


# x view


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
        self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient, row: int = 0, *args, **kwargs: Any
    ) -> None:
        super().__init__(interaction, timeout=kwargs.get('timeout', 600.0), *args, **kwargs)
        self.v_user = v_user
        self.v_client: ValorantClient = client
        self.v_locale = ValorantLocale.from_discord(str(interaction.locale))
        self.riot_auth_list = v_user.get_riot_accounts()
        self._build_buttons(row)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if await super().interaction_check(interaction):
            self.v_locale = ValorantLocale.from_discord(str(interaction.locale))
            return True
        return False

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

    def remove_switch_button(self) -> None:
        self.remove_item_by_type(cls=ButtonAccountSwitchX)

    @staticmethod
    async def _edit_message(message: discord.InteractionMessage, **kwargs: Any) -> None:
        try:
            await message.edit(**kwargs)
        except (discord.HTTPException, discord.NotFound, discord.Forbidden):
            pass

    async def on_timeout(self) -> None:
        self.disable_buttons()
        if self.message is None:
            original_response = await self.interaction.original_response()
            if original_response:
                await self._edit_message(original_response, view=self)
        else:
            await self._edit_message(self.message, view=self)

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        pass

    async def send(self, **kwargs: Any) -> None:
        try:
            if self.message is None:
                self.message = await self.interaction.followup.send(**kwargs, view=self)
                return
            await self.message.edit(**kwargs, view=self)
        except discord.HTTPException:
            pass


class StoreSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=0)

    @alru_cache(maxsize=32)
    async def get_embeds(self, riot_auth: RiotAuth, locale: Optional[valorantx.Locale]) -> List[discord.Embed]:
        sf = await self.v_client.fetch_store_front(riot_auth)  # type: ignore
        return store_e(sf.get_store(), riot_auth, locale=locale)

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embeds = await self.get_embeds(riot_auth, self.v_locale)
        await self.send(embeds=embeds)


class NightMarketSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=0)

    @alru_cache(maxsize=32)
    async def get_embeds(self, riot_auth: RiotAuth, locale: valorantx.Locale) -> List[discord.Embed]:
        sf = await self.v_client.fetch_store_front(riot_auth)  # type: ignore
        nightmarket = sf.get_nightmarket()

        if nightmarket is None:
            raise CommandError(f"{bold('Nightmarket')} is not available.")

        return nightmarket_e(nightmarket, riot_auth, locale=locale)

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embeds = await self.get_embeds(riot_auth, self.v_locale)
        await self.send(embeds=embeds)


class GamePassPageSourceX(ListPageSource['contract.Reward']):
    def __init__(
        self, contracts: valorantx.Contracts, relation_type: valorantx.RelationType, riot_auth: valorantx.RiotAuth
    ) -> None:
        self.type = relation_type
        self.riot_auth = riot_auth
        self.contract = (
            contracts.special_contract()
            if relation_type == valorantx.RelationType.agent
            else contracts.get_latest_contract(relation_type=relation_type)
        )
        super().__init__(self.contract.content.get_all_rewards(), per_page=1)

    async def format_page(self, menu: GamePassSwitchX, page: Any):
        reward = self.entries[menu.current_page]
        return game_pass_e(reward, self.contract, self.type, self.riot_auth, menu.current_page, locale=menu.v_locale)


class GamePassSwitchX(SwitchingViewX, LattePages):
    def __init__(
        self,
        interaction: Interaction,
        v_user: ValorantUser,
        client: ValorantClient,
        relation_type: valorantx.RelationType,
    ) -> None:
        super().__init__(interaction, v_user, client, row=1)
        self.relation_type = relation_type

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        contracts = await self.v_client.fetch_contracts(riot_auth)  # type: ignore
        self.source = GamePassPageSourceX(contracts=contracts, relation_type=self.relation_type, riot_auth=riot_auth)
        self.current_page = self.source.contract.current_tier
        await self.start_pages()


class PointSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=0)

    @alru_cache(maxsize=32)
    async def get_embeds(self, riot_auth: RiotAuth, locale: valorantx.Locale) -> discord.Embed:
        wallet = await self.v_client.fetch_wallet(riot_auth)  # type: ignore
        return wallet_e(wallet, riot_auth, locale=locale)

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embed = await self.get_embeds(riot_auth, self.v_locale)
        await self.send(embed=embed)


class MissionSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=0)

    @alru_cache(maxsize=5)
    async def get_embeds(self, riot_auth: RiotAuth) -> discord.Embed:

        contracts = await self.v_client.fetch_contracts(riot_auth)  # type: ignore
        return mission_e(contracts, riot_auth, locale=self.v_locale)

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        embed = await self.get_embeds(riot_auth)
        await self.send(embed=embed)


class CollectionSwitchX(SwitchingViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=1)
        self.collection: Optional[valorantx.Collection] = None
        # self.wallet: Optional[valorantx.Wallet] = None
        self.mmr: Optional[valorantx.MMR] = None
        self._riot_auth: Optional[RiotAuth] = None
        self.pages: Optional[List[discord.Embed]] = None
        # view cache
        self.skin_view = SkinCollectionViewX(self)
        self.spray_view = SprayCollectionView(self)

    @ui.button(label=_('Skin'), style=ButtonStyle.blurple)
    async def skin(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self.skin_view.start()

    @ui.button(label=_('Spray'), style=ButtonStyle.blurple)
    async def spray(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await self.spray_view.start()

    async def build_pages(
        self, riot_auth: RiotAuth, collection: valorantx.Collection, mmr: valorantx.MMR
    ) -> List[discord.Embed]:

        latest_tier = mmr.get_latest_rank_tier() if mmr is not None else None

        # loadout
        player_title = collection.get_player_title()
        player_card = collection.get_player_card()
        account_level = collection.get_account_level()
        # level_border = collection.get_level_border()

        e = discord.Embed()
        # e.description = '{vp_emoji} {wallet_vp} {rad_emoji} {wallet_rad}'.format(
        #     vp_emoji=wallet.get_valorant().emoji,  # type: ignore
        #     wallet_vp=wallet.valorant_points,
        #     rad_emoji=wallet.get_radiant().emoji,  # type: ignore
        #     wallet_rad=wallet.radiant_points,
        # )

        e.set_author(
            name='{display_name} - Collection'.format(display_name=riot_auth.display_name),
            icon_url=latest_tier.large_icon if latest_tier is not None else None,
        )
        e.set_footer(text='Lv. {level}'.format(level=account_level))

        if player_title is not None:
            e.title = player_title.text_localizations.from_locale(str(self.locale))

        if player_card is not None:
            e.set_image(url=player_card.wide_icon)
            card_color_thief = await self.bot.get_or_fetch_colors(player_card.uuid, player_card.wide_icon)
            e.colour = random.choice(card_color_thief)

        return [e]

    @alru_cache(maxsize=5)
    async def fetch_collection(self, riot_auth: RiotAuth) -> valorantx.Collection:
        return await self.v_client.fetch_collection(riot_auth)  # type: ignore

    @alru_cache(maxsize=5)
    async def fetch_wallet(self, riot_auth: RiotAuth) -> valorantx.Wallet:
        return await self.v_client.fetch_wallet(riot_auth)  # type: ignore

    @alru_cache(maxsize=5)
    async def fetch_mmr(self, riot_auth: RiotAuth) -> valorantx.MMR:
        return await self.v_client.fetch_mmr(riot_auth)  # type: ignore

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        self._riot_auth = riot_auth

        self.collection = await self.fetch_collection(riot_auth)
        # self.wallet = await self.fetch_wallet(riot_auth)
        self.mmr = await self.fetch_mmr(riot_auth)

        self.pages = await self.build_pages(riot_auth, self.collection, self.mmr)

        await self.send(embeds=self.pages)


class SprayCollectionView(ViewAuthor):  # Non-X
    def __init__(self, other_view: CollectionSwitchX) -> None:
        super().__init__(other_view.interaction, timeout=600)
        self.other_view = other_view
        self._pages: List[discord.Embed] = []

    @alru_cache(maxsize=5)
    async def build_pages(self, collection: valorantx.Collection) -> List[discord.Embed]:
        embeds = []
        for slot, spray in enumerate(collection.get_sprays(), start=1):
            # TODO: slot number in spray model
            embed = spray_loadout_e(spray, slot, locale=self.other_view.v_locale)

            if embed._thumbnail.get('url'):
                color_thief = await self.bot.get_or_fetch_colors(spray.uuid, embed._thumbnail['url'])
                embed.colour = random.choice(color_thief)

            embeds.append(embed)
        return embeds

    @ui.button(label=_('Back'), style=discord.ButtonStyle.green, custom_id='back', row=0)
    async def back(self, interaction: Interaction, button: ui.Button):
        self.other_view.reset_timeout()
        await interaction.response.defer()
        await self.other_view.message.edit(embeds=self.other_view.pages, view=self.other_view)

    @ui.button(label=_('Change Spray'), style=discord.ButtonStyle.grey, custom_id='change_spray', row=0, disabled=True)
    async def change_spray(self, interaction: Interaction, button: ui.Button):
        pass

    async def start(self) -> None:
        self._pages = await self.build_pages(self.other_view.collection)
        await self.other_view.message.edit(embeds=self._pages, view=self)


class SkinCollectionSourceX(ListPageSource):
    def __init__(self, collection: valorantx.Collection):
        super().__init__(sorted(list(collection.get_skins()), key=self.sort_skins), per_page=4)

    @staticmethod
    def sort_skins(
        skin_sort: Union[valorantx.SkinLoadout, valorantx.SkinLevelLoadout, valorantx.SkinChromaLoadout]
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

    async def format_page(
        self,
        view: SkinCollectionViewX,
        entries: List[Union[valorantx.SkinLoadout, valorantx.SkinLevelLoadout, valorantx.SkinChromaLoadout]],
    ) -> List[discord.Embed]:
        return [skin_loadout_e(skin, locale=view.other_view.v_locale) for skin in entries]


class SkinCollectionViewX(ViewAuthor, LattePages):
    def __init__(
        self,
        other_view: CollectionSwitchX,
    ) -> None:
        super().__init__(other_view.interaction, timeout=600)
        self.other_view = other_view

    @ui.button(label=_('Back'), style=discord.ButtonStyle.green, custom_id='back', row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        self.other_view.reset_timeout()
        await interaction.response.defer()
        await self.other_view.message.edit(embeds=self.other_view.pages, view=self.other_view)

    @ui.button(label=_('Change Skin'), style=discord.ButtonStyle.grey, custom_id='change_skin', row=1, disabled=True)
    async def change_skin(self, interaction: Interaction, button: ui.Button):
        pass

    async def start(self) -> None:
        self.source = SkinCollectionSourceX(self.other_view.collection)
        self.message = self.other_view.message
        await self.start_pages()


class SelectMatchHistoryX(ui.Select['CarrierSwitchX']):
    def __init__(self, view: CarrierSwitchX) -> None:
        super().__init__(placeholder=_("Select Match to see details"), max_values=1, min_values=1, row=1)
        self._source: List[valorantx.MatchDetails] = []
        self.view_md = MatchDetailsViewX(view.interaction, view)

    def build_selects(self, match_details: List[valorantx.MatchDetails]) -> None:
        self._source = match_details
        for index, match in enumerate(match_details):
            enemy_team = match.get_enemy_team()
            me_team = match.get_me_team()

            players = sorted(match.get_players(), key=lambda p: p.kills, reverse=True)

            left_team_score = me_team.rounds_won if me_team is not None else 0
            right_team_score = enemy_team.rounds_won if enemy_team is not None else 0

            if match.game_mode == valorantx.GameModeType.deathmatch:
                if match.me.is_winner():
                    _2nd_place = (players[1]) if len(players) > 1 else None
                    _1st_place = match.me
                else:
                    _2nd_place = match.me
                    _1st_place = (players[0]) if len(players) > 0 else None

                left_team_score = (_1st_place.kills if match.me.is_winner() else _2nd_place.kills) if _1st_place else 0
                right_team_score = (_2nd_place.kills if match.me.is_winner() else _1st_place.kills) if _2nd_place else 0

            self.add_option(
                label='{won} - {lose}'.format(won=left_team_score, lose=right_team_score),
                value=str(index),
                description='{map} - {queue}'.format(map=match.map.display_name, queue=match.game_mode.display_name),
                emoji=match.me.agent.emoji,  # type: ignore
            )

    def clear_options(self) -> None:
        self.options.clear()

    async def callback(self, interaction: Interaction) -> Any:
        assert self.view is not None
        value = self.values[0]

        self.view.locale = interaction.locale
        await interaction.response.defer()

        if self.view_md.message is None:
            self.view_md.message = self.view.message
        await self.view_md.start(self._source[int(value)])


class CarrierPageSourceX(ListPageSource):
    def __init__(self, data: List[valorantx.MatchDetails], per_page: int = 3):
        super().__init__(data, per_page=per_page)

    @staticmethod
    def default_page(match: valorantx.MatchDetails, locale: valorantx.Locale) -> discord.Embed:

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
            text=f"{match.game_mode.display_name} • {match.map.name_localizations.from_locale(str(locale))}",
            icon_url=match.game_mode.display_icon
            # icon_url=tier.large_icon if tier is not None and match.queue == valorantx.QueueType.competitive else None,
        )
        return embed

    def format_page(self, menu: CarrierSwitchX, entries: List[valorantx.MatchDetails]) -> List[discord.Embed]:
        embeds = []

        # build pages
        for match in entries:
            embeds.append(self.default_page(match, menu.v_locale))

        # build select menu
        for child in menu.children:
            if isinstance(child, SelectMatchHistoryX):
                child.clear_options()
                child.build_selects(entries)

        menu.current_embeds = embeds

        return embeds


class CarrierSwitchX(SwitchingViewX, LattePages):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user, client, row=2)
        # self.mmr: Optional[valorantx.MMR] = None
        self._queue: Optional[str] = None
        self.re_build: bool = False
        self.current_embeds: List[discord.Embed] = []
        self.add_item(SelectMatchHistoryX(self))

    # @staticmethod
    # def tier_embed(mmr: Optional[valorantx.MMR] = None) -> Optional[discord.Embed]:
    #     if mmr is None:
    #         return None
    #     competitive = mmr.get_latest_competitive_season()
    #     if competitive is not None:
    #         parent_season = competitive.season.parent
    #         e = discord.Embed(colour=int(competitive.tier.background_color[:-2], 16), timestamp=datetime.datetime.now())
    #         e.set_author(name=competitive.tier.display_name, icon_url=competitive.tier.large_icon)
    #         e.set_footer(
    #             text=str(competitive.ranked_rating)
    #             + '/100'
    #             + ' • '
    #             + parent_season.display_name
    #             + ' '
    #             + competitive.season.display_name
    #         )
    #         return e
    #     return None

    async def start_pages(self, *, content: Optional[str] = None, ephemeral: bool = False) -> None:
        await super().start_pages(content=content, ephemeral=ephemeral)

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        self._queue = kwargs.pop('queue', self._queue)
        client = self.v_client.set_authorize(riot_auth)
        match_history = await client.fetch_match_history(queue=self._queue)  # type: ignore
        self.source = CarrierPageSourceX(data=match_history.get_match_details())
        # self.mmr = await client.fetch_mmr(riot_auth)
        # TODO: build tier embed
        await self.start_pages()


class MatchDetailsPageSourceX(ListPageSource):
    def __init__(self, match_details: valorantx.MatchDetails) -> None:
        total_pages = 3 if match_details.game_mode != valorantx.GameModeType.deathmatch else 2
        super().__init__(list(i for i in range(0, total_pages)), per_page=1)
        embeds = MatchEmbed(match_details)
        self.desktop = embeds.get_desktop()
        self.mobile = embeds.get_mobile()

    def format_page(self, menu: Any, page: int) -> discord.Embed:
        return self.mobile[page] if menu.is_on_mobile else self.desktop[page]


class MatchDetailsViewX(ViewAuthor, LattePages):

    is_on_mobile: bool = False

    def __init__(self, interaction: Interaction, other_view: Optional[discord.ui.View] = None, **kwargs) -> None:
        super().__init__(interaction, compact=True, timeout=kwargs.pop('timeout', 600.0), **kwargs)

        if member := interaction.guild.get_member(interaction.user.id):
            self.is_on_mobile = member.is_on_mobile()

        self.other_view: Optional[Union[discord.ui.View, CarrierSwitchX]] = other_view
        if self.other_view is None:
            self.remove_item(self.back_to_home)

    @ui.button(emoji='🖥️', style=ButtonStyle.green, custom_id='mobile', row=0)
    async def toggle_ui(self, interaction: Interaction, button: ui.Button) -> None:
        button.emoji = '🖥️' if self.is_on_mobile else '📱'
        self.is_on_mobile = not self.is_on_mobile
        await self.show_checked_page(interaction, 0)

    @ui.button(label=_("Home"), style=ButtonStyle.green, custom_id='home_button')
    async def back_to_home(self, interaction: Interaction, button: ui.Button) -> None:
        if self.other_view is not None:
            self.other_view.reset_timeout()
        await interaction.response.defer()
        await self.message.edit(embeds=self.other_view.current_embeds, view=self.other_view)

    async def start(self, match: valorantx.MatchDetails) -> None:
        self.source = MatchDetailsPageSourceX(match)
        await self.start_pages()


class MatchDetailsSwitchX(SwitchingViewX, MatchDetailsViewX):
    def __init__(self, interaction: Interaction, v_user: ValorantUser, client: ValorantClient) -> None:
        super().__init__(interaction, v_user=v_user, client=client, row=2)
        self._queue: Optional[str] = None

    async def start_view(self, riot_auth: RiotAuth, **kwargs: Any) -> None:
        self._queue = kwargs.pop('queue', self._queue)
        client = self.v_client.set_authorize(riot_auth)
        match_history = await client.fetch_match_history(queue=self._queue, start=0, end=1)  # type: ignore

        if len(match_history.get_match_details()) == 0:
            self.disable_buttons()
            embed = discord.Embed(
                title=_("No matches found"),
                description=_("You have no matches in your match history"),
                color=discord.Color.red(),
            )
            if self.message is None:
                self.message = await self.interaction.edit_original_response(embed=embed, view=self)
            await self.message.edit(embed=embed, view=self)
            return
        self.current_page = 0
        await super().start(match=match_history.get_match_details()[0])

    def disable_buttons(self):
        self.previous_page.disabled = self.next_page.disabled = self.toggle_ui.disabled = True

    async def on_timeout(self) -> None:
        self.clear_items()
        await super().on_timeout()


# code below is for testing purposes


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
