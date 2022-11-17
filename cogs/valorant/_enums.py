from __future__ import annotations

from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Union

import valorantx

if TYPE_CHECKING:
    from typing_extensions import Self


class AgentEmoji(str, Enum):

    astra = '<:agent_astra:1042813586835243050>'
    breach = '<:agent_breach:1042813549484970054>'
    brimstone = '<:agent_brimstone:1042813590354264064>'
    chamber = '<:agent_chamber:1042813558309789716>'
    cypher = '<:agent_cypher:1042813567835050084>'
    fade = '<:agent_fade:1042813612131111063>'
    harbor = '<:agent_harbor:1042813576370454568>'
    jett = '<:agent_jett:1042813609312538814>'
    kay_o = '<:agent_kay_o:1042813561052876902>'
    killjoy = '<:agent_killjoy:1042813573799366686>'
    neon = '<:agent_neon:1042813593722294363>'
    omen = '<:agent_omen:1042813606363938916>'
    phoenix = '<:agent_phoenix:1042813583693721712>'
    raze = '<:agent_raze:1042813552681037855>'
    reyna = '<:agent_reyna:1042813602354176020>'
    sage = '<:agent_sage:1042813598822563892>'
    skye = '<:agent_skye:1042813564521549914>'
    sova = '<:agent_sova:1042813570846576660>'
    viper = '<:agent_viper:1042813580409585704>'
    yoru = '<:agent_yoru:1042813595710410833>'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_agent(cls, agent: Union[valorantx.Agent, str]) -> str:
        try:
            display_name = agent.display_name if isinstance(agent, valorantx.Agent) else agent
            return cls[display_name.lower().replace("/", "_").replace(" ", "_")]
        except KeyError:
            return ''


class ContentTierEmoji(str, Enum):

    deluxe = '<:content_tier_deluxe:1042810257426108557>'
    exclusive = '<:content_tier_exclusive:1042810259317735434>'
    premium = '<:content_tier_premium:1042810261289050224>'
    select = '<:content_tier_select:1042810263361036360>'
    ultra = '<:content_tier_ultra:1042810265906991104>'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_name(cls, content_tier: Union[valorantx.ContentTier, str]) -> str:
        try:
            name = content_tier.dev_name if isinstance(content_tier, valorantx.ContentTier) else content_tier
            return cls[name.lower()]
        except KeyError:
            return ''


class RoundResultEmoji(str, Enum):
    diffuse_loss = '<:diffuseloss:1042809400592715816>'
    diffuse_win = '<:diffusewin:1042809402526281778>'
    elimination_loss = '<:eliminationloss:1042809418661761105>'
    elimination_win = '<:eliminationwin:1042809420549206026>'
    explosion_loss = '<:explosionloss:1042809464274812988>'
    explosion_win = '<:explosionwin:1042809466137083996>'
    time_loss = '<:timeloss:1042809483270832138>'
    time_win = '<:timewin:1042809485128896582>'
    surrendered = '<:EarlySurrender_Flag:1042829113741819996>'

    def __str__(self) -> str:
        return str(self.value)


class PointEmoji(Enum):

    valorant = '<:currency_valorant:1042817047953952849>'
    radianite = '<:currency_radianite:1042817896398737417>'
    free_agent = '<:currency_free_agents:1042817043965165580>'

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
