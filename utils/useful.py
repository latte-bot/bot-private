from __future__ import annotations

import enum
from typing import Any, Iterable, Tuple, Union

import discord

__all__: Tuple[str, ...] = ('Palette', 'LatteEmbed', 'LatteFonts', 'LatteImages', 'LatteCDN')

IMAGE_PATH = 'assets/images/'
FONT_PATH = 'assets/fonts/'
CHANNEL_ID = 1001848697316987009
BASE_URL = 'https://cdn.discordapp.com/' + 'attachments/' + str(CHANNEL_ID)


class Palette(discord.Color):
    def __init__(self, palette: Tuple[int, int, int]) -> None:
        super().__init__(value=(palette[0] << 16) + (palette[1] << 8) + palette[2])


# thanks stella_bot ---
class LatteEmbed(discord.Embed):
    """Main purpose is to get the usual setup of Embed for a command or an error embed"""

    def __init__(
        self,
        color: Union[discord.Color, int] = 0xFFFFFF,
        fields: Iterable[Tuple[str, str]] = (),
        field_inline: bool = False,
        **kwargs: Any,
    ):
        super().__init__(color=color, **kwargs)
        for n, v in fields:
            self.add_field(name=n, value=v, inline=field_inline)

    @classmethod
    def default(cls, **kwargs) -> LatteEmbed:
        instance = cls(**kwargs)
        return instance

    @classmethod
    def to_error(cls, color: Union[discord.Color, int] = 0xFF7878, **kwargs) -> LatteEmbed:
        return cls(color=color, **kwargs)


# ---


class LatteFonts(enum.Enum):

    dinnextw1g_bold: str = FONT_PATH + 'DINNextW1G-Bold.otf'
    dinnextw1g_regular: str = FONT_PATH + 'DINNextW1G-Regular.otf'
    beni_bold: str = FONT_PATH + 'BeniBold.ttf'
    serif_712: str = FONT_PATH + '712_serif.ttf'

    def __str__(self) -> str:
        return str(self.value)


class LatteImages(enum.Enum):

    pre_collection = IMAGE_PATH + 'pre-collection.png'
    profile_card_available = IMAGE_PATH + 'profile_card_available.png'
    profile_card_available_2 = IMAGE_PATH + 'profile_card_available_2.png'
    profile_card_away = IMAGE_PATH + 'profile_card_away.png'
    profile_card_in_match = IMAGE_PATH + 'profile_card_in_match.png'
    profile_card_offline = IMAGE_PATH + 'profile_card_offline.png'
    invite_banner = IMAGE_PATH + 'invite_banner.png'
    help_banner = IMAGE_PATH + 'help_banner.png'

    def __str__(self) -> str:
        return str(self.value)


class LatteCDN(enum.Enum):

    help_banner: str = str(BASE_URL) + '/1001848873385472070/help_banner.png'
    invite_banner: str = str(BASE_URL) + '/1001858419990478909/invite_banner.png'

    def __str__(self) -> str:
        return str(self.value)
