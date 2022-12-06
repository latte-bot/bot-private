from typing import List

import discord
from discord import ui
from discord.types.interactions import ModalSubmitComponentInteractionData as ModalSubmitComponentInteractionDataPayload

# https://github.com/InterStella0/stella_bot/blob/master/utils/modal.py


class BaseModal(ui.Modal):
    def reset_timeout(self) -> None:
        self.timeout = self.timeout

    async def _scheduled_task(
        self, interaction: discord.Interaction, components: List[ModalSubmitComponentInteractionDataPayload]
    ):
        try:
            self._refresh_timeout()
            self._refresh(interaction, components)

            allow = await self.interaction_check(interaction)
            if not allow:
                return await self.on_check_failure(interaction)

            await self.on_submit(interaction)

            # auto defer
            if not interaction.response.type:
                await interaction.response.defer()

        except Exception as e:
            return await self.on_error(interaction, e)
        else:
            # No error, so assume this will always happen
            # In the future, maybe this will require checking if we set an error response.
            self.stop()

    async def on_check_failure(self, interaction: discord.Interaction) -> None:
        """coro

        A callback that is called when the interaction check fails.

        Parameters
        ----------
        interaction: Interaction
            The interaction that failed the check.
        """
        pass
