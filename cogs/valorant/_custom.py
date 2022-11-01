import valorantx

from typing import TYPE_CHECKING, Mapping, Any, List, Dict, Optional

if TYPE_CHECKING:
    from ._client import Client

class Ability(valorantx.models.agent.Ability):
    def __init__(self, client: Client, data: Dict[str, Any], agent_name: Optional[str] = None) -> None:
        super().__init__(client, data)
        self.custom_id: Optional[str] = self.__build_custom_id(agent_name)

    def __build_custom_id(self, value: str) -> str:
        return (value.lower() + '_' + self.display_name.lower()).replace('/', '_').replace(' ', '_').replace('___', '_').replace('__', '_').replace("'", '')

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
            client=self._client, data=ability, agent_name=self.display_name
        ) for ability in self._abilities]
