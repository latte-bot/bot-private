from __future__ import annotations

import enum
from typing import Any, Iterable, Tuple, Union

import discord

_asset_path = 'assets/'
_asset_image_path = _asset_path + 'images/'
_asset_font_path = _asset_path + 'fonts/'

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

    dinnextw1g_bold: str = _asset_font_path + 'DINNextW1G-Bold.otf'
    dinnextw1g_regular: str = _asset_font_path + 'DINNextW1G-Regular.otf'
    beni_bold: str = _asset_font_path + 'BeniBold.ttf'
    serif_712: str = _asset_font_path + '712_serif.ttf'

    def __str__(self) -> str:
        return self.value


class LatteImages(enum.Enum):

    pre_collection = _asset_image_path + 'pre-collection.png'
    profile_card_available = _asset_image_path + 'profile_card_available.png'
    profile_card_available_2 = _asset_image_path + 'profile_card_available_2.png'
    profile_card_away = _asset_image_path + 'profile_card_away.png'
    profile_card_in_match = _asset_image_path + 'profile_card_in_match.png'
    profile_card_offline = _asset_image_path + 'profile_card_offline.png'
    invite_banner = _asset_image_path + 'invite_banner.png'
    help_banner = _asset_image_path + 'help_banner.png'

    def __str__(self) -> str:
        return self.value


class LatteCDN(enum.Enum):

    __base_url__: str = 'https://cdn.discordapp.com/'
    __cdn_guild_id__ = 1001848697316987009
    __attachments__: str = __base_url__ + 'attachments/' + str(__cdn_guild_id__) + '/'

    help_banner: str = __attachments__ + '1001848873385472070/help_banner.png'
    invite_banner: str = __attachments__ + '1001858419990478909/invite_banner.png'

    def __str__(self) -> str:
        return self.value
