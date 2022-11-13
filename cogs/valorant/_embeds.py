from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Tuple, Union

import discord
import valorantx
from async_lru import alru_cache
from discord import Interaction
from valorantx.models import Bundle

from utils.chat_formatting import bold
from utils.formats import format_relative

from ._enums import ContentTier as ContentTierEmoji, Point as PointEmoji, ValorantLocale as VLocale

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
                title=f"{emoji} {bold(skin.name_localizations.from_locale_code(str(locale)))}",
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
        self, contract: valorantx.Contracts, riot_acc: RiotAuth, *, locale: Optional[Union[str, VLocale]] = None
    ) -> List[discord.Embed]:

        locale = locale or self.locale

        btp = contract.get_latest_contract(relation_type=valorantx.RelationType.season)

        next_reward = btp.get_next_reward()

        embed = discord.Embed(
            title=f"Battlepass for {bold(riot_acc.display_name)}",
            description=f"{bold('NEXT')}: {next_reward.display_name}",
        )
        embed.set_footer(text=f'TIER {btp.current_tier} | {btp.name_localizations.from_locale_code(str(locale))}')

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
            title="EMOJI {}".format(partial_item.name_localizations.american_english),
            description="VP {}".format(partial_item.price),
            color=color,
        )
        if partial_item.icon is not None:
            embed.set_thumbnail(url=partial_item.icon)
        return embed

    base_e = Embed(
        title=bundle.name_localizations.american_english,
        description="VP {}".format(bundle.price),
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

    # https://github.com/staciax/reinabot/blob/master/cogs/valorant/embeds.py

    def __init__(self):
        self.client = ...

    @staticmethod
    def static_embed(performance: bool = False) -> discord.Embed:
        e = discord.Embed(
            title="{queue_emoji} {map_name_locale} - {match_score}",
            # color=color,
            # timestamp=timestamp
        )
        e.set_footer(text="{match_result}")

        # if not performance:
        #     e.set_author(name="{your_name} - {queue['name']}", icon_url="your_agent['icon']['small']")
        # else:
        #     e.set_author(name='{your_name} - Performance', icon_url="your_agent['icon']['small']")

        return e

    # desktop section

    # page 1
    def desktop_page_1(self) -> discord.Embed:
        e = self.static_embed()
        # e.add_field(name='TEAM A', value='\n'.join(team_A['players']))
        # e.add_field(name='ACS', value='\n'.join(team_A['acs']))
        # e.add_field(name='KDA', value='\n'.join(team_A['kda']))
        # e.add_field(name='TEAM B', value='\n'.join(team_B['players']))
        # e.add_field(name='ACS', value='\n'.join(team_B['acs']))
        # e.add_field(name='KDA', value='\n'.join(team_B['kda']))
        # if not queue_id == 'ggteam':
        #     if len(timelines) > 25:
        #         e.add_field(name='Timeline:', value=''.join(timelines[:25]), inline=False)
        #         e.add_field(name='Overtime:', value=''.join(timelines[25:]), inline=False)
        #     else:
        #         e.add_field(name='Timeline:', value=''.join(timelines), inline=False)

        return e

    # page 2
    def desktop_page_2(self) -> discord.Embed:
        e = self.static_embed()
        # e.add_field(name='TEAM A', value='\n'.join(team_A['players']))
        # e.add_field(name='FK', value='\n'.join(team_A['first_blood']))
        # e.add_field(name='HS%', value='\n'.join(team_A['headshots']))
        # e.add_field(name='TEAM B', value='\n'.join(team_B['players']))
        # e.add_field(name='FK', value='\n'.join(team_B['first_blood']))
        # e.add_field(name='HS%', value='\n'.join(team_B['headshots']))

        return e

    # page 3

    def desktop_page_3(self) -> discord.Embed:
        e = self.static_embed(performance=True)
        # e.add_field(name='KDA', value='\n'.join(opponent['kda']))
        # e.add_field(name='Opponent', value='\n'.join(opponent['players']))
        # if queue_id not in ['ggteam']:
        #     e.add_field(name='Abilities', value=your_abilities, inline=False)

        return e

    # mobile section

    # page 1
    # page 2
    # page 3
