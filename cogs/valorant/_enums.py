from enum import Enum


class ContentTier(Enum):

    deluxe = '<:Content_Deluxe:1000264410637545602>'
    exclusive = '<:Content_Exclusive:1000264453226516510>'
    premium = '<:Content_Premium:1000264438932316221>'
    select = '<:Content_Select:1000264389410164778>'
    ultra = '<:Content_Ultra:1000264517651017818>'

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_name(cls, name: str) -> str:
        value = getattr(cls, name.lower(), None)
        if value is None:
            raise ValueError(f'Invalid content tier: {name}')
        return value.value


class Point(Enum):

    valorant_point = '<:_ValorantPoint:1000270198441521242>'
    radianite_point = '<:_RadianitePoint:1000270183585284166>'
    free_agent = '<:_FreeAgent:1000270307145306162>'

    def __str__(self) -> str:
        return str(self.value)


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
    def from_discord(cls, value: str) -> str:
        value = value.replace('-', '_')
        locale = getattr(cls, value, None)
        if locale is None:
            raise ValueError(f'Invalid locale: {value}')
        return str(locale)
