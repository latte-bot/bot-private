import valorantx

from typing import TYPE_CHECKING, Mapping, Any, List, Dict, Optional

if TYPE_CHECKING:
    from ._client import Client

class Ability(valorantx.models.agent):
    def __init__(self, client: Client, data: Dict[str, Any], custom_id: Optional[str] = None) -> None:
        super().__init__(client, data)
        self.custom_id: Optional[str] = custom_id

    @property
    def emoji(self) -> str:
        return ...

class Agent(valorantx.Agent):

    def __init__(self, client: Client, data: Mapping[str, Any]) -> None:
        super().__init__(client, data)

    @property
    def abilities(self) -> List[Ability]:
        """:class: `List[AgentAbility]` Returns the agent's abilities."""
        return [Ability(
            client=self._client, data=ability, custom_id=self.display_name
        ) for ability in self._abilities]
