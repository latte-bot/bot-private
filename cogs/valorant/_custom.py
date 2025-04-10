from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Union

import valorantx
from valorantx import CurrencyType, GameModeType
from valorantx.models import match

from ._enums import AbilitiesEmoji, AgentEmoji, ContentTierEmoji, GameModeEmoji, PointEmoji, RoundResultEmoji, TierEmoji

if TYPE_CHECKING:
    from ._client import Client


class Ability(valorantx.AgentAbility):
    def __init__(self, client: Client, data: Dict[str, Any], agent: Optional[valorantx.Agent] = None) -> None:
        super().__init__(client, data)
        self.emoji_key: str = '' if agent is None else self.__build_emoji_key(agent.display_name)

    def __build_emoji_key(self, value: str) -> str:
        return (
            (value.lower() + '_' + self.display_name.lower())
            .replace('/', '_')
            .replace(' ', '_')
            .replace('___', '_')
            .replace('__', '_')
            .replace("'", '')
        )

    @property
    def emoji(self) -> str:
        return AbilitiesEmoji.get(self.emoji_key)


class Agent(valorantx.Agent):
    @property
    def abilities(self) -> List[Ability]:
        """:class: `List[AgentAbility]` Returns the agent's abilities."""
        return [Ability(client=self._client, data=ability, agent=self) for ability in self._abilities]

    @property
    def emoji(self) -> str:
        return AgentEmoji.get(self.display_name)


class Currency(valorantx.Currency):
    @property
    def emoji(self) -> str:
        return str(PointEmoji.valorant) if self.uuid == str(CurrencyType.valorant) else str(PointEmoji.radianite)


class Tier(valorantx.Tier):
    @property
    def emoji(self) -> str:
        return TierEmoji.get(self.display_name)


class CompetitiveTier(valorantx.CompetitiveTier):
    @property
    def tiers(self) -> List[Tier]:
        """:class: `list` Returns the competitive tier's tiers."""
        return [Tier(client=self._client, data=tier) for tier in self._tiers]


class ContentTier(valorantx.ContentTier):
    @property
    def emoji(self) -> str:
        return ContentTierEmoji.get(self.dev_name)


class MatchRoundResult(match.RoundResult):
    @property
    def emoji(self) -> str:
        return RoundResultEmoji.get(str(self.result_code), self.winning_team() == self.match.me.team)


class GameMode(valorantx.GameMode):
    def __init__(self, client: Client, data: Mapping[str, Any], **kwargs) -> None:
        super().__init__(client=client, data=data)
        self._display_name: Union[str, Dict[str, str]] = data['displayName']
        self._is_ranked: bool = kwargs.get('is_ranked', False)
        self.__display_name_override()

    @property
    def emoji(self) -> str:
        return GameModeEmoji.get(self.display_name)

    def is_ranked(self) -> bool:
        """:class: `bool` Returns whether the game mode is ranked."""
        return self._is_ranked

    def __display_name_override(self) -> None:
        if self.uuid == '96bd3920-4f36-d026-2b28-c683eb0bcac5':
            if self._is_ranked:
                self._display_name = {
                    "ar-AE": "تنافسي",
                    "de-DE": "Gewertet",
                    "en-US": "Competitive",
                    "es-ES": "Competitivo",
                    "es-MX": "Competitivo",
                    "fr-FR": "Compétition",
                    "id-ID": "Competitive",
                    "it-IT": "Competitiva",
                    "ja-JP": "コンペティティブ",
                    "ko-KR": "경쟁전",
                    "pl-PL": "Rankingowa",
                    "pt-BR": "Competitivo",
                    "ru-RU": "рейтинговaя игра",
                    "th-TH": "Competitive",
                    "tr-TR": "Rekabete dayalı",
                    "vi-VN": "thi đấu xếp hạng",
                    "zh-CN": "競技模式",
                    "zh-TW": "競技模式",
                }
            else:
                self._display_name = {
                    "ar-AE": "غير مصنف",
                    "de-DE": "Ungewertet",
                    "en-US": "Unrated",
                    "es-ES": "No competitivo",
                    "es-MX": "Normal",
                    "fr-FR": "Non classé",
                    "id-ID": "Unrated",
                    "it-IT": "Non competitiva",
                    "ja-JP": "アンレート",
                    "ko-KR": "일반전",
                    "pl-PL": "Nierankingowa",
                    "pt-BR": "Sem classificação",
                    "ru-RU": "БЕЗ Рaнгa",
                    "th-TH": "Unrated",
                    "tr-TR": "Derecesiz",
                    "vi-VN": "Đấu Thường",
                    "zh-CN": "一般模式",
                    "zh-TW": "一般模式",
                }


class MatchDetails(valorantx.MatchDetails):
    def __init__(self, client: Client, data: Any) -> None:
        super().__init__(client=client, data=data)
        self._round_results: List[MatchRoundResult] = (
            [MatchRoundResult(self, data) for data in data['roundResults']] if data.get('roundResults') else []
        )

    @property
    def game_mode(self) -> Optional[GameMode]:
        """:class:`GameMode`: The game mode this match was played in."""
        return self._client.get_game_mode(uuid=GameModeType.from_url(self._game_mode), is_ranked=self._is_ranked)
