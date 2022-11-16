from __future__ import annotations

from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Union

import valorantx

if TYPE_CHECKING:
    from typing_extensions import Self


class AgentEmoji(str, Enum):

    astra = ''
    breach = ''
    brimstone = ''
    chamber = ''
    cypher = ''
    fade = ''
    harbor = ''
    jett = ''
    kay_o = ''
    killjoy = ''
    neon = ''
    omen = ''
    phoenix = ''
    raze = ''
    reyna = ''
    sage = ''
    skye = ''
    sova = ''
    viper = ''
    yoru = ''

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_agent(cls, agent: Union[valorantx.Agent, str]) -> str:
        try:
            display_name = agent.display_name if isinstance(agent, valorantx.Agent) else agent
            return cls[display_name.lower().replace("/", "_").replace(" ", "_")]
        except KeyError:
            return ''


class ContentTier(str, Enum):

    deluxe = '<:Content_Deluxe:1000264410637545602>'
    exclusive = '<:Content_Exclusive:1000264453226516510>'
    premium = '<:Content_Premium:1000264438932316221>'
    select = '<:Content_Select:1000264389410164778>'
    ultra = '<:Content_Ultra:1000264517651017818>'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_name(cls, content_tier: Union[valorantx.ContentTier, str]) -> str:
        try:
            name = content_tier.dev_name if isinstance(content_tier, valorantx.ContentTier) else content_tier
            return cls[name.lower()]
        except KeyError:
            return ''


class Point(Enum):

    valorant_point = '<:_ValorantPoint:1000270198441521242>'
    radianite_point = '<:_RadianitePoint:1000270183585284166>'
    free_agent = '<:_FreeAgent:1000270307145306162>'

    def __str__(self) -> str:
        return str(self.value)


class ResultColor(IntEnum):
    win = 0x60DCC4
    lose = 0xFC5C5C
    draw = 0xCBCCD6


class ValorantLocale(Enum):
    en_US = 'en-US'
    en_GB = 'en-US'
    zh_CN = 'zh-CN'
    zh_TW = 'zh-TW'
    fr = 'fr-FR'
    de = 'de-DE'
    it = 'it-IT'
    ja = 'ja-JP'
    ko = 'ko-KR'
    pl = 'pl-PL'
    pt_BR = 'pt-BR'
    ru = 'ru-RU'
    es_ES = 'es-ES'
    th = 'th-TH'
    tr = 'tr-TR'
    vi = 'vi-VN'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_discord(cls, value: str) -> Self:
        value = value.replace('-', '_')
        locale = getattr(cls, value, None)
        if locale is None:
            raise ValueError(f'Invalid locale: {value}')
        return locale
