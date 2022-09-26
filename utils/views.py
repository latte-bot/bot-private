from __future__ import annotations

import logging
import time
from typing import Any

import discord
from discord import Interaction, ui
from discord.ext import commands

from .useful import LatteEmbed

_log = logging.getLogger(__name__)


def key(interaction: discord.Interaction) -> discord.User:
    return interaction.user


class Button(ui.Button):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# thanks stella_bot
class BaseView(ui.View):
    def reset_timeout(self) -> None:
        self.timeout = self.timeout

    async def _scheduled_task(self, item: discord.ui.item, interaction: discord.Interaction):
        try:

            item._refresh_state(interaction.data)  # type: ignore

            if self.timeout:
                self.__timeout_expiry = time.monotonic() + self.timeout

            allow = await self.interaction_check(interaction)
            if not allow:
                return

            await item.callback(interaction)

            if not interaction.response._response_type:
                await interaction.response.defer()

        except Exception as e:
            return await self.on_error(interaction, e, item)

    async def on_error(self, interaction: Interaction, error: Exception, item: ui.Item[Any]) -> None:
        # TODO: supress error

        embed = LatteEmbed.to_error(title="Error occurred:", description=str(error))
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

        _log.exception(error)


# thanks stella_bot
class ViewAuthor(BaseView):
    def __init__(self, interaction: Interaction, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.interaction = interaction
        self.is_command = interaction.command is not None
        self.cooldown = commands.CooldownMapping.from_cooldown(1, 10, key)

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Only allowing the context author to interact with the view"""

        author = self.interaction.user
        user = interaction.user

        if await self.interaction.client.is_owner(user):  # type: ignore
            return True

        if isinstance(user, discord.Member) and user.guild_permissions.administrator:
            return True

        if user != author:
            bucket = self.cooldown.get_bucket(interaction)
            if not bucket.update_rate_limit():
                if self.is_command:

                    command_name: str = self.interaction.command.qualified_name
                    app_cmd_mapping: dict = self.interaction.client._app_commands  # type: ignore

                    get_app_cmd = app_cmd_mapping.get(command_name)

                    if get_app_cmd is not None:
                        app_cmd = f'{get_app_cmd.mention}'
                    else:
                        app_cmd = f'/`{command_name}`'

                    content = f"Only {author.mention} can use this. If you want to use it," f" use {app_cmd}"
                else:
                    content = f"Only `{author}` can use this."
                embed = LatteEmbed.to_error(description=content)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
