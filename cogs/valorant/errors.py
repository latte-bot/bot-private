import discord
from discord import app_commands

from ._abc import MixinMeta
from ._errors import NoAccountsLinked


class ErrorHandler(MixinMeta):  # noqa
    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:

        if not isinstance(error, NoAccountsLinked):
            return await super().cog_app_command_error(interaction, error)  # type: ignore
