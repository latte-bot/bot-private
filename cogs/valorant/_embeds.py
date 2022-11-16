from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Tuple, Union

import discord
import valorantx
from async_lru import alru_cache
from discord import Interaction
from valorantx import QueueID
from valorantx.models import Bundle

from utils.chat_formatting import bold
from utils.formats import format_relative

from ._enums import ContentTier as ContentTierEmoji, Point as PointEmoji, ResultColor, ValorantLocale as VLocale

if TYPE_CHECKING:
    from discord import Client

    from bot import LatteBot

    from ._client import RiotAuth

    ClientBot = Union[Client, LatteBot]


class MakeEmbed:
    def __init__(self, interaction: Interaction) -> None:
        self.interaction = interaction
        self.bot: ClientBot = interaction.client
        self.locale: str = VLocale.from_discord(str(interaction.locale))
        self.embeds: List[discord.Embed] = []

    @alru_cache(maxsize=5)
    async def build_store(
        self,
        store_front: valorantx.StoreFront,
        riot_acc: RiotAuth,
        *,
        locale: Optional[Union[str, VLocale]] = None,
    ) -> List[discord.Embed]:
        locale = locale or self.locale

        store = store_front.get_store()

        embeds = [
            Embed(
                description=f"Daily store for {bold(riot_acc.display_name)}\n"  # type: ignore
                f"Resets {format_relative(store.reset_at)}"
            )
        ]

        for skin in store.get_skins():
            emoji = ContentTierEmoji.from_name(skin.rarity.dev_name)
            e = Embed(
                title=f"{emoji} {bold(skin.name_localizations.from_locale(str(locale)))}",
                description=f"{PointEmoji.valorant_point} {skin.price}",
                colour=self.bot.theme.dark,
            )
            if skin.display_icon is not None:
                e.url = skin.display_icon.url
                e.set_thumbnail(url=skin.display_icon.url)
            embeds.append(e)

        self.embeds = embeds
        return embeds

    @alru_cache(maxsize=5)
    async def build_battlepass(
        self,
        contract: valorantx.Contracts,
        riot_acc: RiotAuth,
        *,
        locale: Optional[Union[str, VLocale]] = None,
    ) -> List[discord.Embed]:

        locale = locale or self.locale

        btp = contract.get_latest_contract(relation_type=valorantx.RelationType.season)

        next_reward = btp.get_next_reward()

        embed = discord.Embed(
            title=f'Battlepass for {bold(riot_acc.display_name)}',
            description=f"{bold('NEXT')}: {next_reward.display_name}",
        )
        embed.set_footer(text=f'TIER {btp.current_tier} | {btp.name_localizations.from_locale(str(locale))}')

        if isinstance(next_reward, valorantx.SkinLevel):
            if next_reward.display_icon is not None:
                embed.set_thumbnail(url=next_reward.display_icon)
        elif isinstance(next_reward, valorantx.PlayerCard):
            if next_reward.wide_icon is not None:
                embed.set_thumbnail(url=next_reward.wide_icon)
            else:
                if next_reward.display_icon is not None:
                    embed.set_thumbnail(url=next_reward.display_icon)
        else:
            if not isinstance(next_reward, valorantx.PlayerTitle):
                if next_reward.display_icon is not None:
                    embed.set_thumbnail(url=next_reward.display_icon)

        if btp.current_tier <= 50:
            embed.colour = self.bot.theme.purple
        else:
            embed.colour = self.bot.theme.gold

        self.embeds = [embed]
        return [embed]


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


# def store_e(offer: StoreOffer) -> List[Embed]:
#
#     e_list = [
#         Embed(description="Daily store for **{username}** \nResets {duration}"),
#     ]
#
#     for skin in offer.skins:
#         e = Embed(description=f"{skin.tier} **{skin.name_localizations.american_english}**\n VP {skin.price}")
#         if skin.icon is not None:
#             e.set_thumbnail(url=skin.icon)
#         e_list.append(e)
#
#     return e_list
#
# def store_e(offer: StoreOffer) -> List[Embed]:
#
#     e_list = [
#         Embed(description="Daily store for **{username}** \nResets {duration}"),
#     ]
#
#     for skin in offer.skins:
#         e = Embed(description=f"{skin.tier} **{skin.name_localizations.american_english}**\n VP {skin.price}")
#         if skin.icon is not None:
#             e.set_thumbnail(url=skin.icon)
#         e_list.append(e)
#
#     return e_list


# def wallet_e(wallet: Wallet) -> Embed:
#     e = Embed(title=f"Point:")
#     e.add_field(name='vp', value=f"{wallet.valorant_points}")
#     e.add_field(name='rad', value=f"{wallet.radiant_points}")
#     e.set_footer(text=wallet._client.user.display_name)
#
#     return e


def bundles_e(bundle: Bundle) -> List[Embed]:
    def static_item_embed(partial_item: Any, *, color: Union[discord.Color, int] = 0x0F1923) -> Embed:
        embed = Embed(
            title='EMOJI {}'.format(partial_item.name_localizations.american_english),
            description='VP {}'.format(partial_item.price),
            color=color,
        )
        if partial_item.icon is not None:
            embed.set_thumbnail(url=partial_item.icon)
        return embed

    base_e = Embed(
        title=bundle.name_localizations.american_english,
        description='VP {}'.format(bundle.price),
    )

    e_list = [
        base_e,
    ]

    # for item in bundle.items:
    #     e_list.append(static_item_embed(item))

    return e_list


# member_from_cache = interaction.guild.get_member(interaction.user.id)
# cache from voice


class MatchEmbed:
    def __init__(self, match: valorantx.MatchDetails):
        self._match = match
        self._desktops: List[discord.Embed] = []
        self._mobiles: List[discord.Embed] = []

        # map
        self._map = self._match.map

        # me team
        self._mt = self._match.get_me_team()
        self._mt_players = sorted(self._mt.get_players(), key=lambda p: p.acs, reverse=True)

        # enemy team
        self._et = self._match.get_enemy_team()
        self._et_players = sorted(self._et.get_players(), key=lambda p: p.acs, reverse=True)

    def get_desktop(self) -> List[discord.Embed]:
        return [self.desktop_1(), self.desktop_2(), self.desktop_3()]

    # def get_mobile(self) -> List[discord.Embed]:
    #     return []

    def static_embed(self, performance: bool = False) -> discord.Embed:

        e = discord.Embed(
            title='{queue_emoji} {map} - {won}:{lose}'.format(
                queue_emoji='🔥',
                map=self._map.display_name,
                won=self._mt.rounds_won,
                lose=self._et.rounds_won,
            ),
            timestamp=self._match.started_at,
            # color=color,
        )
        e.set_footer(text='{match_result}')

        e.set_author(
            name='{0} - {1}'.format(
                self._match.me.display_name,
                (self._match.queue if performance else 'Performance'),
            ),
            icon_url=self._match.me.agent.display_icon_small,
        )

        if self._match.team_blue.rounds_won == self._match.team_red.rounds_won:
            e.colour = ResultColor.draw
        elif self._match.me.is_winner():
            e.colour = ResultColor.win
        else:
            e.colour = ResultColor.lose

        return e

    # desktop section
    def desktop_1(self) -> discord.Embed:

        e = self.static_embed()

        # MY TEAM
        e.add_field(
            name='MY TEAM',
            value='\n'.join(
                [(bold(p.display_name) if p == self._match.me else p.display_name) for p in self._mt_players]
            ),
        )
        e.add_field(name='ACS', value="\n".join([str(int(p.acs)) for p in self._mt_players]))
        e.add_field(name='KDA', value="\n".join([str(p.kda) for p in self._mt_players]))

        # ENEMY TEAM
        e.add_field(
            name='ENEMY TEAM',
            value='\n'.join([p.display_name for p in self._et_players]),
        )
        e.add_field(name='ACS', value="\n".join([str(int(p.acs)) for p in self._et_players]))
        e.add_field(name='KDA', value="\n".join([str(p.kda) for p in self._et_players]))

        timelines = []

        for i, r in enumerate(self._match.round_results, start=1):

            if r.result_code == valorantx.RoundResultCode.surrendered:
                timelines.append('Surrendered')
                break

            if i == 12:
                timelines.append(' | ')

            if r.winning_team() == self._mt:
                timelines.append('🟢')
            else:
                timelines.append('🔴')

        if not self._match.queue == QueueID.escalation:
            if len(timelines) > 25:
                e.add_field(name='Timeline:', value=''.join(timelines[:25]), inline=False)
                e.add_field(name='Overtime:', value=''.join(timelines[25:]), inline=False)
            else:
                e.add_field(name='Timeline:', value=''.join(timelines), inline=False)

        return e

    def desktop_2(self) -> discord.Embed:

        e = self.static_embed()

        # MY TEAM
        e.add_field(
            name='MY TEAM',
            value='\n'.join(
                [(bold(p.display_name) if p == self._match.me else p.display_name) for p in self._mt_players]
            ),
        )
        e.add_field(name='FK', value="\n".join([str(p.first_kills) for p in self._mt_players]))
        e.add_field(
            name='HS%',
            value='\n'.join([(str(round(p.head_shot_percent, 1)) + '%') for p in self._mt_players]),
        )

        # ENEMY TEAM
        e.add_field(
            name='ENEMY TEAM',
            value='\n'.join([p.display_name for p in self._et_players]),
        )
        e.add_field(name='FK', value='\n'.join([str(p.first_kills) for p in self._et_players]))
        e.add_field(
            name='HS%',
            value='\n'.join([(str(round(p.head_shot_percent, 1)) + '%') for p in self._et_players]),
        )

        return e

    def desktop_3(self) -> discord.Embed:
        e = self.static_embed(performance=True)
        e.add_field(
            name='KDA',
            value='\n'.join(
                [
                    p.kda_opponent
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
                p.opponent.display_name
                for p in sorted(
                    self._match.me.opponents,
                    key=lambda p: p.opponent.display_name.lower(),
                )
            ),
        )

        if not self._match.queue == QueueID.escalation:
            abilities = self._match.me.ability_casts
            text = '{c_casts} {q_casts} {e_casts} {x_casts}'.format(
                c_casts=round(abilities.c_casts / self._match.me.rounds_played, 1),
                e_casts=round(abilities.e_casts / self._match.me.rounds_played, 1),
                q_casts=round(abilities.q_casts / self._match.me.rounds_played, 1),
                x_casts=round(abilities.x_casts / self._match.me.rounds_played, 1),
            )
            e.add_field(name='Abilities', value=text, inline=False)

        return e

    # mobile section
    # page 1
    # page 2
    # page 3
