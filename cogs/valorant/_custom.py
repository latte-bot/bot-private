from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Union

import valorantx
from valorantx import CurrencyID, RoundResultCode

from ._enums import ContentTierEmoji as ContentTierEmoji, PointEmoji, AgentEmoji, RoundResultEmoji
from valorantx.models.match import RoundResult

if TYPE_CHECKING:
    from ._client import Client


class Ability(valorantx.AgentAbility):
    def __init__(self, client: Client, data: Dict[str, Any], agent_name: Optional[str] = None) -> None:
        super().__init__(client, data)
        self.custom_id: str = self.__build_custom_id(agent_name)

    def __build_custom_id(self, value: str) -> str:
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
        return ''


class Agent(valorantx.Agent):
    def __init__(self, client: Client, data: Mapping[str, Any]) -> None:
        super().__init__(client, data)

    @property
    def abilities(self) -> List[Ability]:
        """:class: `List[AgentAbility]` Returns the agent's abilities."""
        return [Ability(client=self._client, data=ability, agent_name=self.display_name) for ability in self._abilities]

    @property
    def emoji(self) -> str:
        return AgentEmoji.from_agent(self.display_name)


class Currency(valorantx.Currency):
    def __init__(self, client: Client, data: Mapping[str, Any]) -> None:
        super().__init__(client, data)

    @property
    def emoji(self) -> str:
        return (
            str(PointEmoji.valorant)
            if self.uuid == str(CurrencyID.valorant_point)
            else str(PointEmoji.radianite)
        )


class Tier(valorantx.Tier):
    def __init__(self, client: Client, data: Mapping[str, Any]) -> None:
        super().__init__(client, data)

    @property
    def emoji(self) -> str:
        return ''


class CompetitiveTier(valorantx.CompetitiveTier):
    def __init__(self, client: Client, data: Mapping[str, Any]) -> None:
        super().__init__(client=client, data=data)

    @property
    def tiers(self) -> List[Tier]:
        """:class: `list` Returns the competitive tier's tiers."""
        return [Tier(client=self._client, data=tier) for tier in self._tiers]


class ContentTier(valorantx.ContentTier):
    def __init__(self, client: Client, data: Mapping[str, Any]) -> None:
        super().__init__(client=client, data=data)

    @property
    def emoji(self) -> str:
        return ContentTierEmoji.from_name(self.dev_name)


class RoundResult(RoundResult):

    def __init__(self, match: MatchDetails, data: Any) -> None:
        super().__init__(match, data)

    @property
    def emoji(self) -> str:
        if self.result_code != RoundResultCode.surrendered:
            if self.winning_team() == self.match.me.team:
                if self.result_code == RoundResultCode.defuse:
                    return RoundResultEmoji.diffuse_win
                elif self.result_code == RoundResultCode.elimination:
                    return RoundResultEmoji.elimination_win
                elif self.result_code == RoundResultCode.detonate:
                    return RoundResultEmoji.explosion_win
                else:
                    return RoundResultEmoji.time_loss
            else:
                if self.result_code == RoundResultCode.defuse:
                    return RoundResultEmoji.diffuse_loss
                elif self.result_code == RoundResultCode.elimination:
                    return RoundResultEmoji.elimination_loss
                elif self.result_code == RoundResultCode.detonate:
                    return RoundResultEmoji.explosion_loss
                else:
                    return RoundResultEmoji.time_win
        else:
            return RoundResultEmoji.surrendered


class GameMode(valorantx.GameMode):

    def __init__(self, client: Client, data: Mapping[str, Any]) -> None:
        super().__init__(client=client, data=data)
        self._display_name: Union[str, Dict[str, str]] = data['displayName']
        self._is_ranked: bool = False

    @property
    def emoji(self) -> str:
        return ''

    def __display_name_x(self, name: str) -> None:
        self._display_name = name
        competitive = {
            "ar-AE": "تنافسي",
            "de-DE": "Gewertet",
            "en-US": "Competitive",
            "es-ES": "Competitiva",
            "es-MX": "Clasificatoria",
            "fr-FR": "Compétition",
            "id-ID": "Competitive",
            "it-IT": "Competitiva",
            "ja-JP": "コンペティティブ",
            "ko-KR": "경쟁전",
            "pl-PL": "Rankingowej",
            "pt-BR": "Competitiva",
            "ru-RU": "рейтинговую",
            "th-TH": "Competitive",
            "tr-TR": "Rekabete dayalı",
            "vi-VN": "thi đấu xếp hạng",
            "zh-CN": "競技模式",
            "zh-TW": "競技模式"
        }
        unrated = {
            "ar-AE": "",
            "de-DE": "Ungewertet",
            "en-US": "Unrated",
            "es-ES": "",
            "es-MX": "",
            "fr-FR": "Non classé",
            "id-ID": "Unrated",
            "it-IT": "",
            "ja-JP": "",
            "ko-KR": "",
            "pl-PL": "",
            "pt-BR": "",
            "ru-RU": "",
            "th-TH": "Unrated",
            "tr-TR": "Derecesiz",
            "vi-VN": "Đấu Thường",
            "zh-CN": "",
            "zh-TW": ""
        }



class MatchDetails(valorantx.MatchDetails):
    def __init__(self, client: Client, data: Any) -> None:
        super().__init__(client=client, data=data)
        self._round_results: List[RoundResult] = (
            [RoundResult(self, data) for data in data['roundResults']] if data.get('roundResults') else []
        )