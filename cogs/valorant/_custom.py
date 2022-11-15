from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import valorantx
from valorantx import CurrencyID

from ._enums import ContentTier as ContentTierEmoji, Point as PointEmoji

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
        return ''


class Currency(valorantx.Currency):
    def __init__(self, client: Client, data: Mapping[str, Any]) -> None:
        super().__init__(client, data)

    @property
    def emoji(self) -> str:
        return (
            str(PointEmoji.valorant_point)
            if self.uuid == str(CurrencyID.valorant_point)
            else str(PointEmoji.radianite_point)
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
