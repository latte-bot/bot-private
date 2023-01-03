from __future__ import annotations

import datetime
import random
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Tuple, Union

import discord
import valorantx

# from async_lru import alru_cache
from valorantx import GameModeType, MissionType

from utils.chat_formatting import bold, italics, strikethrough
from utils.enums import Theme
from utils.formats import format_relative
from utils.i18n import _

from ._enums import PointEmoji, ResultColor

if TYPE_CHECKING:
    from discord import Client

    from bot import LatteBot
    ClientBot = Union[Client, LatteBot]
    from valorantx.models import contract, match

    from ._client import RiotAuth

    SkinLoadout = Union[valorantx.SkinLoadout, valorantx.SkinLevelLoadout, valorantx.SkinChromaLoadout]
    SprayLoadout = Union[valorantx.SprayLoadout, valorantx.SprayLevelLoadout]

BundleItem = Union[valorantx.Skin, valorantx.Buddy, valorantx.Spray, valorantx.PlayerCard]
FeaturedBundleItem = Union[
    valorantx.SkinBundle, valorantx.SprayBundle, valorantx.BuddyBundle, valorantx.PlayerCardBundle
]
SkinItem = Union[valorantx.Skin, valorantx.SkinLevel, valorantx.SkinChroma]
SprayItem = Union[valorantx.Spray, valorantx.SprayLevel]
BuddyItem = Union[valorantx.Buddy, valorantx.BuddyLevel]


class Embed(discord.Embed):
    def __init__(
        self,
        color: Union[discord.Color, int] = 0xFD4554,
        fields: Iterable[Tuple[str, str]] = (),
        field_inline: bool = False,
        **kwargs,
    ):
        super().__init__(color=color, **kwargs)
        for n, v in fields:
            self.add_field(name=n, value=v, inline=field_inline)


def skin_e(
    skin: Union[valorantx.Skin, valorantx.SkinLevel, valorantx.SkinChroma],
    locale: valorantx.Locale,
    *,
    is_nightmarket: bool = False,
) -> discord.Embed:
    embed = Embed(
        title=f"{skin.rarity.emoji} {bold(skin.name_localizations.from_locale(str(locale)))}",
        colour=Theme.purple,
    )

    if not is_nightmarket:
        embed.description = f'{PointEmoji.valorant} {bold(skin.price)}'
    else:
        embed.description = (
            f'{PointEmoji.valorant} {bold(str(skin.discount_price))}\n'
            f'{PointEmoji.valorant} {strikethrough(str(skin.price))} (-{skin.discount_percent}%)'
        )

    if skin.display_icon is not None:
        embed.url = skin.display_icon.url
        embed.set_thumbnail(url=skin.display_icon)

    if skin.rarity is not None:
        embed.colour = int(skin.rarity.highlight_color[0:6], 16)

    return embed


def store_e(
    store: valorantx.StoreOffer, riot_auth: RiotAuth, *, locale: Optional[valorantx.Locale] = None
) -> List[discord.Embed]:

    locale = riot_auth.locale if locale is None else locale

    embeds = [
        Embed(
            description=_('Daily store for {user}\n').format(user=bold(riot_auth.display_name))
            + f'Resets {format_relative(store.reset_at)}',
            colour=Theme.purple,
        )
    ]

    for skin in store.get_skins():
        embeds.append(skin_e(skin, locale))

    return embeds


def nightmarket_e(
    nightmarket: valorantx.NightMarketOffer, riot_auth: RiotAuth, *, locale: Optional[valorantx.Locale] = None
) -> List[discord.Embed]:

    locale = riot_auth.locale if locale is None else locale

    embeds = [
        Embed(
            description=f'NightMarket for {bold(riot_auth.display_name)}\n'
            f'Expires {format_relative(nightmarket.expire_at)}',
            colour=Theme.purple,
        )
    ]

    for skin in nightmarket.get_skins():
        embeds.append(skin_e(skin, locale, is_nightmarket=True))

    return embeds


def wallet_e(
    wallet: valorantx.Wallet, riot_auth: RiotAuth, *, locale: Optional[valorantx.Locale] = None
) -> discord.Embed:

    vp = wallet.get_valorant()
    rad = wallet.get_radiant()

    vp_name = vp.name_localizations.from_locale(str(locale))

    embed = embed = Embed(title=f'{riot_auth.display_name} Point:')

    embed.add_field(
        name=f'{(vp_name if vp_name != "VP" else "Valorant")}',
        value=f'{vp.emoji} {wallet.valorant_points}',  # type: ignore
    )
    embed.add_field(
        name=f'{rad.name_localizations.from_locale(str(locale)).removesuffix(" Points")}',
        value=f'{rad.emoji} {wallet.radiant_points}',  # type: ignore
    )
    return embed


def game_pass_e(
    reward: contract.Reward,
    contract: contract.ContractU,
    relation_type: valorantx.RelationType,
    riot_auth: RiotAuth,
    page: int,
    *,
    locale: Optional[valorantx.Locale] = None,
) -> discord.Embed:

    item = reward.get_item()

    if relation_type is valorantx.RelationType.agent:
        display_name = 'Agent'
    elif relation_type is valorantx.RelationType.event:
        display_name = 'Eventpass'
    else:
        display_name = 'Battlepass'
    embed = discord.Embed(
        title='{gamepass} for {display_name}'.format(gamepass=display_name, display_name=bold(riot_auth.display_name))
    )
    embed.set_footer(
        text='TIER {tier} | {gamepass}'.format(
            tier=page + 1, gamepass=contract.name_localizations.from_locale(str(locale))
        )
    )

    if item is not None:
        embed.description = '{item}'.format(item=item.display_name)
        if not isinstance(item, valorantx.PlayerTitle):
            if item.display_icon is not None:
                if isinstance(item, valorantx.SkinLevel):
                    embed.set_image(url=item.display_icon)
                elif isinstance(item, valorantx.PlayerCard):
                    embed.set_image(url=item.wide_icon)
                # elif isinstance(item, valorantx.Agent):
                #     embed.set_image(url=item.full_portrait_v2 or item.full_portrait)
                else:
                    embed.set_thumbnail(url=item.display_icon)

    return embed


def mission_e(
    contracts: valorantx.Contracts, riot_auth: RiotAuth, *, locale: Optional[valorantx.Locale] = None
) -> discord.Embed:
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

    embed = Embed(title='{display_name} Mission:'.format(
        display_name=riot_auth.display_name
    ))
    if all_completed:
        embed.colour = 0x77DD77

    if len(daily) > 0:
        embed.add_field(
            name=f"**Daily**",
            value='\n'.join(daily),
            inline=False,
        )

    if len(weekly) > 0:

        embed.add_field(
            name=f"**Weekly**",
            value='\n'.join(weekly)
            + '\n\n Refill Time: {refill_time}'.format(
                refill_time=format_relative(contracts.mission_metadata.weekly_refill_time)
                if contracts.mission_metadata.weekly_refill_time is not None
                else '-'
            ),
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

    return embed


def skin_loadout_e(skin: SkinLoadout, *, locale: valorantx.Locale = valorantx.Locale.american_english) -> discord.Embed:

    if isinstance(skin, valorantx.SkinChromaLoadout):
        _skin = skin.get_skin()
        if _skin is not None:
            skin_dn = _skin.name_localizations.from_locale(str(locale))
        else:
            skin_dn = skin.name_localizations.from_locale(str(locale))
    else:
        skin_dn = skin.name_localizations.from_locale(str(locale))

    embed = discord.Embed(
        description=(skin.rarity.emoji if skin.rarity is not None else '')  # type: ignore
        + ' '
        + bold(skin_dn)
        + (' ★' if skin.is_favorite() else ''),
        colour=int(skin.rarity.highlight_color[0:6], 16) if skin.rarity is not None else Theme.dark,
    )
    embed.set_thumbnail(url=skin.display_icon)

    buddy = skin.get_buddy()
    if buddy is not None:
        buddy_dn = buddy.name_localizations.from_locale(str(locale))
        embed.set_footer(
            text=f'{buddy_dn}' + (' ★' if buddy.is_favorite() else ''),
            icon_url=buddy.display_icon,
        )
    return embed


def spray_loadout_e(
    spray: SprayLoadout, slot: int, *, locale: valorantx.Locale = valorantx.Locale.american_english
) -> discord.Embed:
    spray_dn = spray.name_localizations.from_locale(str(locale))
    embed = discord.Embed(description=bold(str(slot) + '. ' + spray_dn) + (' ★' if spray.is_favorite() else ''))
    spray_icon = spray.animation_gif or spray.full_transparent_icon or spray.display_icon
    if spray_icon is not None:
        embed.set_thumbnail(url=spray_icon)
    return embed


def patch_notes_e(pn: valorantx.PatchNote, banner_url: Optional[str] = None) -> discord.Embed:
    embed = discord.Embed(
        title=pn.title,
        timestamp=pn.timestamp.replace(tzinfo=datetime.timezone.utc),
        url=pn.url,
        description=italics(pn.description),
    )
    embed.set_image(url=(banner_url or pn.banner))
    return embed


def agent_e(agent: valorantx.Agent, *, locale: valorantx.Locale = valorantx.Locale.american_english) -> discord.Embed:
    embed = Embed(
        title=agent.name_localizations.from_locale(str(locale)),
        description=italics(agent.description_localizations.from_locale(str(locale))),
        colour=int(random.choice(agent.background_gradient_colors)[:-2], 16),
    )
    embed.set_image(url=agent.full_portrait)
    embed.set_thumbnail(url=agent.display_icon)
    embed.set_footer(
        text=agent.role.name_localizations.from_locale(str(locale)),
        icon_url=agent.role.display_icon,
    )
    return embed


def buddy_e(
    buddy: Union[valorantx.Buddy, valorantx.BuddyLevel], *, locale: valorantx.Locale = valorantx.Locale.american_english
) -> discord.Embed:
    embed = Embed(colour=Theme.purple)
    if isinstance(buddy, valorantx.Buddy):
        embed.set_author(
            name=buddy.name_localizations.from_locale(str(locale)),
            icon_url=buddy.theme.display_icon if buddy.theme is not None else None,
            url=buddy.display_icon,
        )

    elif isinstance(buddy, valorantx.BuddyLevel):
        embed.set_author(
            name=buddy._base_buddy.name_localizations.from_locale(str(locale)),
            url=buddy.display_icon,
            icon_url=buddy._base_buddy.theme.display_icon if buddy._base_buddy.theme is not None else None,
        )
    embed.set_image(url=buddy.display_icon)

    return embed


def spray_e(
    spray: Union[valorantx.Spray, valorantx.SprayLevel], *, locale: valorantx.Locale = valorantx.Locale.american_english
) -> discord.Embed:
    embed = Embed(colour=Theme.purple)

    if isinstance(spray, valorantx.Spray):
        embed.set_author(
            name=spray.name_localizations.from_locale(str(locale)),
            url=spray.display_icon,
            icon_url=spray.theme.display_icon if spray.theme is not None else None,
        )
        embed.set_image(url=spray.animation_gif or spray.full_transparent_icon or spray.display_icon)

    elif isinstance(spray, valorantx.SprayLevel):
        base_spray = spray.get_base_spray()
        embed.set_author(
            name=base_spray.name_localizations.from_locale(str(locale)),
            icon_url=base_spray.theme.display_icon if base_spray.theme is not None else None,
            url=spray.display_icon,
        )
        embed.set_image(
            url=base_spray.animation_gif
            or base_spray.full_transparent_icon
            or base_spray.display_icon
            or spray.display_icon
        )


def player_card_e(
    player_card: valorantx.PlayerCard, *, locale: valorantx.Locale = valorantx.Locale.american_english
) -> discord.Embed:
    embed = Embed(colour=Theme.purple)
    embed.set_author(
        name=player_card.name_localizations.from_locale(str(locale)),
        icon_url=player_card.theme.display_icon if player_card.theme is not None else None,
        url=player_card.large_icon,
    )
    embed.set_image(url=player_card.large_icon)
    return embed


def bundle_item_e(
    item: Union[BundleItem, FeaturedBundleItem],
    is_featured: bool = False,
    *,
    locale: valorantx.Locale = valorantx.Locale.american_english,
) -> discord.Embed:
    emoji = item.rarity.emoji if isinstance(item, valorantx.Skin) else ''  # type: ignore

    embed = Embed(
        title='{rarity} {name}'.format(rarity=emoji, name=bold(item.name_localizations.from_locale(str(locale)))),
        description='{emoji} '.format(emoji=PointEmoji.valorant),
        colour=Theme.dark,
    )
    if not is_featured or item.is_melee():
        embed.description += '{free} {price}'.format(
            free=(bold('FREE') if is_featured else ''), price=(strikethrough(item.price) if is_featured else item.price)
        )
    else:
        if item.discounted_price != item.price and item.discounted_price != 0:
            embed.description += '{discounted} {price}'.format(
                discounted=bold(str(item.discounted_price)), price=strikethrough(str(item.price))
            )
        else:
            embed.description += str(item.price)

    if isinstance(item, valorantx.PlayerCard):
        item_icon = item.large_icon
    elif isinstance(item, valorantx.Spray):
        item_icon = item.animation_gif or item.full_transparent_icon or item.full_icon or item.display_icon
    else:
        item_icon = item.display_icon

    if item_icon is not None:
        embed.url = item_icon.url
        embed.set_thumbnail(url=item_icon)

    return embed


def bundle_e(
    bundle: Union[valorantx.Bundle, valorantx.FeaturedBundle],
    *,
    locale: valorantx.Locale = valorantx.Locale.american_english,
) -> List[discord.Embed]:
    embeds = []

    embed = Embed(colour=Theme.purple)
    if bundle.display_icon_2 is not None:
        embed.set_image(url=bundle.display_icon_2)

    if isinstance(bundle, valorantx.FeaturedBundle):
        embed.description = 'Featured Bundle: {bundle}\n{emoji} {price} {strikethrough} {expires}'.format(
            bundle=bold(bundle.name_localizations.from_locale(str(locale)) + ' Collection'),
            emoji=PointEmoji.valorant,
            price=bold(str(bundle.discount_price)),
            strikethrough=strikethrough(str(bundle.price)),
            expires=italics('(Expires {expires})'.format(expires=format_relative(bundle.expires_at))),
        )
    else:
        embed.description = 'Bundle: {bundle}\n{emoji} {price}'.format(
            bundle=bold(bundle.name_localizations.from_locale(str(locale)) + ' Collection'),
            emoji=PointEmoji.valorant,
            price=bundle.price,
        )

    embeds.append(embed)

    def item_priorities(i: Union[BundleItem, FeaturedBundleItem]) -> int:
        if i.is_melee():
            return 0
        elif isinstance(i, SkinItem):
            return 1
        elif isinstance(i, BuddyItem):
            return 2
        elif isinstance(i, valorantx.PlayerCard):
            return 3
        elif isinstance(i, SprayItem):
            return 4
        # elif isinstance(i, valorantx.PlayerTitle):
        #     return 5
        else:
            return 5

    for item in sorted(bundle.items, key=item_priorities):
        embeds.append(bundle_item_e(item, isinstance(bundle, valorantx.FeaturedBundle), locale=locale))

    return embeds


class MatchEmbed:
    def __init__(self, match: valorantx.MatchDetails):
        self._match = match
        self._desktops: List[discord.Embed] = []
        self._mobiles: List[discord.Embed] = []
        self._build()

    def get_desktop(self) -> List[discord.Embed]:
        return self._desktops

    def get_mobile(self) -> List[discord.Embed]:
        return self._mobiles

    @property
    def me(self) -> Optional[match.MatchPlayer]:
        return self._match.me

    @property
    def _map(self) -> valorantx.Map:
        return self._match.map

    def get_me_team(self) -> Any:  # TODO: fix this
        return self._match.get_me_team()

    def get_enemy_team(self) -> Any:  # TODO: fix this
        return self._match.get_enemy_team()

    def get_me_team_players(self) -> List[match.MatchPlayer]:
        return sorted(self.get_me_team().get_players(), key=lambda p: p.acs, reverse=True)

    def get_enemy_team_players(self) -> List[match.MatchPlayer]:
        return sorted(self.get_enemy_team().get_players(), key=lambda p: p.acs, reverse=True)

    def _get_mvp_star(self, player: match.MatchPlayer) -> str:
        if player == self._match.get_match_mvp():
            return '★'
        elif player == self._match.get_team_mvp():
            return '☆'
        return ''

    def _tier_display(self, player: match.MatchPlayer) -> str:
        tier = player.get_competitive_rank()
        return (
            (' ' + tier.emoji + ' ')  # type: ignore
            if self._match.queue == valorantx.QueueType.competitive and tier is not None
            else ''
        )

    def _player_display(self, player: match.MatchPlayer, is_bold: bool = True) -> str:
        return (
            player.agent.emoji  # type: ignore
            + self._tier_display(player)
            + ' '
            + (bold(player.display_name) if is_bold and player == self.me else player.display_name)
        )

    def _acs_display(self, player: match.MatchPlayer, star: bool = True) -> str:
        acs = str(int(player.acs))
        if star:
            acs += ' ' + self._get_mvp_star(player)
        return acs

    # @lru_cache(maxsize=2)
    def static_embed(self, performance: bool = False) -> discord.Embed:

        me_team = self.get_me_team()
        enemy_team = self.get_enemy_team()

        e = discord.Embed(
            title='{mode} {map} - {won}:{lose}'.format(
                mode=self._match.game_mode.emoji,  # type: ignore
                map=self._map.display_name,
                won=me_team.rounds_won if me_team is not None else 0,
                lose=enemy_team.rounds_won if enemy_team is not None else 0,
            ),
            timestamp=self._match.started_at,
            colour=ResultColor.win,
        )

        if self._match.game_mode == GameModeType.deathmatch:
            players = self._match.get_players()

            if self.me.is_winner():
                _2nd_place = (sorted(players, key=lambda p: p.kills, reverse=True)[1]) if len(players) > 1 else None
                _1st_place = self.me
            else:
                _2nd_place = self.me
                _1st_place = (sorted(players, key=lambda p: p.kills, reverse=True)[0]) if len(players) > 0 else None

            e.title = '{mode} {map} - {won}:{lose}'.format(
                mode=self._match.game_mode.emoji,  # type: ignore
                map=self._map.display_name,
                won=(_1st_place.kills if self.me.is_winner() else _2nd_place.kills) if _1st_place else 0,
                lose=(_2nd_place.kills if self.me.is_winner() else _1st_place.kills) if _2nd_place else 0,
            )

        e.set_author(
            name='{author} - {page}'.format(
                author=self.me.display_name,
                page=(self._match.game_mode.display_name if not performance else 'Performance'),
            ),
            icon_url=self.me.agent.display_icon_small,
        )

        result = 'VICTORY'

        if self._match.game_mode == GameModeType.deathmatch:
            if self.me.is_winner():
                result = '1ST PLACE'
            else:
                players = sorted(self._match.get_players(), key=lambda p: p.kills, reverse=True)
                for index, player in enumerate(players, start=1):
                    player_before = players[index - 1]
                    player_after = players[index] if len(players) > index else None
                    if player == self.me:
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

        elif not self.me.is_winner():
            e.colour = ResultColor.lose
            result = 'DEFEAT'

        if self._match.team_blue is not None and self._match.team_red is not None:
            if self._match.team_blue.rounds_won == self._match.team_red.rounds_won:
                e.colour = ResultColor.draw
                result = 'DRAW'

        e.set_footer(text=result)

        return e

    def __abilities_text(self, abilities: match.AbilityCasts) -> str:
        return '{c_emoji} {c_casts} {q_emoji} {q_casts} {e_emoji} {e_casts} {x_emoji} {x_casts}'.format(
            c_emoji=abilities.c.emoji,  # type: ignore
            c_casts=round(abilities.c_casts / self.me.rounds_played, 1),
            e_emoji=abilities.e.emoji,  # type: ignore
            e_casts=round(abilities.e_casts / self.me.rounds_played, 1),
            q_emoji=abilities.q.emoji,  # type: ignore
            q_casts=round(abilities.q_casts / self.me.rounds_played, 1),
            x_emoji=abilities.x.emoji,  # type: ignore
            x_casts=round(abilities.x_casts / self.me.rounds_played, 1),
        )

    # desktop section
    def desktop_1(self) -> discord.Embed:

        e = self.static_embed()

        mt_players = self.get_me_team_players()
        et_players = self.get_enemy_team_players()

        if self._match.game_mode != GameModeType.deathmatch:
            # MY TEAM
            e.add_field(
                name='MY TEAM',
                value='\n'.join([self._player_display(p) for p in mt_players]),
            )
            e.add_field(
                name='ACS',
                value="\n".join([self._acs_display(p) for p in mt_players]),
            )
            e.add_field(name='KDA', value="\n".join([str(p.kda) for p in mt_players]))

            # ENEMY TEAM
            e.add_field(
                name='ENEMY TEAM',
                value='\n'.join([self._player_display(p, is_bold=False) for p in et_players]),  # type: ignore
            )
            e.add_field(
                name='ACS',
                value="\n".join([self._acs_display(p) for p in et_players]),
            )
            e.add_field(name='KDA', value="\n".join([str(p.kda) for p in et_players]))
        else:
            players = sorted(self._match.get_players(), key=lambda p: p.score, reverse=True)
            e.add_field(
                name='Players',
                value='\n'.join([self._player_display(p) for p in players]),
            )
            e.add_field(name='SCORE', value='\n'.join([f'{p.score}' for p in players]))
            e.add_field(name='KDA', value='\n'.join([f'{p.kda}' for p in players]))

        timelines = []

        for i, r in enumerate(self._match.round_results, start=1):

            if i == 12:
                timelines.append(' | ')

            if r.winning_team() == self.get_me_team():
                timelines.append(r.emoji)  # type: ignore
            else:
                timelines.append(r.emoji)  # type: ignore

            if r.result_code == valorantx.RoundResultCode.surrendered:
                break

        if self._match.game_mode.uuid not in [str(GameModeType.escalation), str(GameModeType.deathmatch)]:
            if len(timelines) > 25:
                e.add_field(name='Timeline:', value=''.join(timelines[:25]), inline=False)
                e.add_field(name='Overtime:', value=''.join(timelines[25:]), inline=False)
            else:
                e.add_field(name='Timeline:', value=''.join(timelines), inline=False)

        return e

    def desktop_2(self) -> discord.Embed:

        e = self.static_embed()

        mt_players = self.get_me_team_players()
        et_players = self.get_enemy_team_players()

        # MY TEAM
        e.add_field(
            name='MY TEAM',
            value='\n'.join([self._player_display(p) for p in mt_players]),
        )
        e.add_field(name='FK', value="\n".join([str(p.first_kills) for p in mt_players]))
        e.add_field(
            name='HS%',
            value='\n'.join([(str(round(p.head_shot_percent, 1)) + '%') for p in mt_players]),
        )

        # ENEMY TEAM
        e.add_field(
            name='ENEMY TEAM',
            value='\n'.join([self._player_display(p, is_bold=False) for p in et_players]),  # type: ignore
        )
        e.add_field(name='FK', value='\n'.join([str(p.first_kills) for p in et_players]))
        e.add_field(
            name='HS%',
            value='\n'.join([(str(round(p.head_shot_percent, 1)) + '%') for p in et_players]),
        )

        return e

    def desktop_3(self) -> discord.Embed:
        e = self.static_embed(performance=True)
        e.add_field(
            name='KDA',
            value='\n'.join(
                [
                    p.kda
                    for p in sorted(
                        self._match.me.opponents,
                        key=lambda p: p.opponent.display_name.lower(),
                    )
                ]
            ),
        )
        e.add_field(
            name='Opponent',
            value='\n'.join(
                self._player_display(p.opponent)
                for p in sorted(
                    self._match.me.opponents,
                    key=lambda p: p.opponent.display_name.lower(),
                )
            ),
        )

        abilities = self._match.me.ability_casts
        if abilities is not None:
            text = self.__abilities_text(abilities)
            e.add_field(name='Abilities', value=text, inline=False)

        return e

    # mobile section
    def mobile_1(self) -> discord.Embed:

        e = self.static_embed()

        if self._match.game_mode != GameModeType.deathmatch:

            # MY TEAM
            e.add_field(name='\u200b', value=bold('MY TEAM'), inline=False)
            for player in self.get_me_team_players():
                e.add_field(
                    name=self._player_display(player),
                    value=f'ACS: {self._acs_display(player)}\nKDA: {player.kda}',
                    inline=True,
                )

            # ENEMY TEAM
            e.add_field(name='\u200b', value=bold('ENEMY TEAM'), inline=False)
            for player in self.get_enemy_team_players():
                e.add_field(
                    name=self._player_display(player),  # type: ignore
                    value=f'ACS: {self._acs_display(player)}\nKDA: {player.kda}',
                    inline=True,
                )
        else:
            players = sorted(self._match.get_players(), key=lambda p: p.score, reverse=True)
            for player in players:
                e.add_field(
                    name=self._player_display(player),  # type: ignore
                    value=f'SCORE: {player.score}\nKDA: {player.kda}',
                    inline=True,
                )

        timelines = []

        for i, r in enumerate(self._match.round_results, start=1):

            # if r.result_code == valorantx.RoundResultCode.surrendered:
            #     timelines.append('Surrendered')
            #     break

            if i == 12:
                timelines.append(' | ')

            if r.winning_team() == self.get_me_team():
                timelines.append(r.emoji)  # type: ignore
            else:
                timelines.append(r.emoji)  # type: ignore

        if self._match.game_mode.uuid not in [str(GameModeType.escalation), str(GameModeType.deathmatch)]:
            if len(timelines) > 25:
                e.add_field(name='Timeline:', value=''.join(timelines[:25]), inline=False)
                e.add_field(name='Overtime:', value=''.join(timelines[25:]), inline=False)
            else:
                e.add_field(name='Timeline:', value=''.join(timelines), inline=False)

        return e

    def mobile_2(self) -> discord.Embed:

        e = self.static_embed()

        # MY TEAM
        e.add_field(name='\u200b', value=bold('MY TEAM'))
        for player in self.get_me_team_players():
            e.add_field(
                name=self._player_display(player),  # type: ignore
                value=f'FK: {player.first_kills}\nHS%: {round(player.head_shot_percent, 1)}%',
                inline=True,
            )

        # ENEMY TEAM
        e.add_field(name='\u200b', value=bold('ENEMY TEAM'), inline=False)
        for player in self.get_enemy_team_players():
            e.add_field(
                name=self._player_display(player, is_bold=False),
                value=f'FK: {player.first_kills}\nHS%: {round(player.head_shot_percent, 1)}%',
                inline=True,
            )

        return e

    def mobile_3(self) -> discord.Embed:
        e = self.static_embed(performance=True)
        e.add_field(
            name='KDA Opponent',
            value='\n'.join(
                [(p.kda + ' ' + self._player_display(p.opponent)) for p in self._match.me.opponents]
            ),  # type: ignore
        )

        abilities = self._match.me.ability_casts
        if abilities is not None:
            text = self.__abilities_text(abilities)
            e.add_field(name='Abilities', value=text, inline=False)

        return e

    def death_match_desktop(self) -> discord.Embed:
        players = sorted(self._match.get_players(), key=lambda p: p.score, reverse=True)
        e = discord.Embed()
        e.set_author(name=self._match.game_mode.display_name, icon_url=self._match.me.agent.display_icon)
        e.add_field(
            name='Players',
            value='\n'.join([self._player_display(p) for p in players]),
        )
        e.add_field(name='SCORE', value='\n'.join([f'{p.score}' for p in players]))
        e.add_field(name='KDA', value='\n'.join([f'{p.kda}' for p in players]))
        return e

    def death_match_mobile(self) -> discord.Embed:
        players = sorted(self._match.get_players(), key=lambda p: p.score, reverse=True)
        e = discord.Embed()
        e.set_author(name=self._match.game_mode.display_name, icon_url=self._match.me.agent.display_icon)
        for player in players:
            e.add_field(
                name=self._player_display(player),  # type: ignore
                value=f'SCORE: {player.score}\nKDA: {player.kda}',
                inline=True,
            )
        return e

    def _build(self) -> None:
        if self._match.game_mode == GameModeType.deathmatch:
            self._desktops = [self.desktop_1(), self.desktop_3()]
            self._mobiles = [self.mobile_1(), self.mobile_3()]
        else:
            self._desktops = [self.desktop_1(), self.desktop_2(), self.desktop_3()]
            self._mobiles = [self.mobile_1(), self.mobile_2(), self.mobile_3()]
