from __future__ import annotations

from typing import Any, Iterable, List, Tuple, Union

import discord

# from valorant.models.store import Wallet
from valorant.models import Bundle

# from valorant.weapon import Skin
# from valorant.spray import Spray
# from valorant.player_card import PlayerCard
# from valorant.player_title import PlayerTitle


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
