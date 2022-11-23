from __future__ import annotations

import io
import logging
import traceback
from typing import TYPE_CHECKING, Union

import discord
import valorantx
from discord import Interaction
from discord.app_commands import (
    AppCommandError,
    BotMissingPermissions,
    CheckFailure,
    CommandInvokeError,
    CommandNotFound,
    CommandOnCooldown,
    CommandSignatureMismatch,
    MissingPermissions,
)
from discord.ext import commands
from jishaku.paginators import PaginatorInterface, WrappedPaginator

from utils.errors import LatteAppError
from utils.i18n import _
from utils.views import ViewAuthor

if TYPE_CHECKING:
    from bot import LatteBot

_log = logging.getLogger('cogs.errors')

# TODO error view

# class ErrorView(ViewAuthor):
#     def __init__(self, interaction: Interaction, user_traceback: Any):
#         super().__init__(interaction)
#         self.error = user_traceback
#
#     @discord.ui.button(label='Report a bug')
#     async def report_error_button(self, interaction: Interaction, button: discord.ui.Button) -> None:
#         error_id = interaction.user.id

# class ReportButton(discord.ui.Button['ViewAuthor']):
#     def __init__(self, original_traceback: traceback):
#         super().__init__(label='Report a bug')
#         self.original_traceback = original_traceback
#
#     async def callback(self, interaction: Interaction) -> Any:
#         assert self.view is not None
#
#         await self.traceback_log.send


class ErrorHandler(commands.Cog):
    """Error handler"""

    def __init__(self, bot: LatteBot) -> None:
        self.bot: LatteBot = bot
        self.bot.tree.on_error = self.on_application_command_error

    @property
    def display_emoji(self) -> discord.Emoji:
        return self.bot.get_emoji(1000812850715054150)

    @discord.utils.cached_property
    def traceback_log(self) -> discord.abc.TextChannel:
        channel = self.bot.get_channel(1002816710593749052)
        return channel

    async def on_application_command_error(self, interaction: Interaction, error: AppCommandError):
        """Handles errors for all application commands associated with this CommandTree."""

        # content = getattr(error, 'original', error)

        if isinstance(error, (discord.Forbidden, discord.NotFound)):
            return

        # traceback
        traceback.print_exception(type(error), error, error.__traceback__)  # TODO: remove this when release

        async def send_error(*args, **kwargs) -> None:
            if interaction.response.is_done():
                await interaction.followup.send(*args, **kwargs, ephemeral=True)
            else:
                await interaction.response.send_message(*args, **kwargs, ephemeral=True)

        view = ViewAuthor(interaction)

        if isinstance(error, (valorantx.RateLimited, valorantx.RiotRatelimitError)):
            content = _("You are being rate limited. Please try again later.")
        elif isinstance(error, valorantx.RiotAuthenticationError):
            content = _("Invalid Riot Username or Password")
        elif isinstance(error, valorantx.HTTPException):
            content = _("Error occurred while fetching data from Valorant API")
        elif isinstance(error, valorantx.RiotUnknownErrorTypeError):
            content = _("Unknown error occurred while fetching data from Valorant API")
        elif isinstance(error, LatteAppError):
            content = getattr(error, 'original', error)
        elif isinstance(error, CommandNotFound):
            content = _('Command not found')
        elif isinstance(error, MissingPermissions):
            content = _('You do not have the required permissions to use this command')
        elif isinstance(error, BotMissingPermissions):
            content = _('I do not have the required permissions to use this command')
        elif isinstance(error, CommandOnCooldown):
            content = _('This command is on cooldown for {cd} seconds').format(cd=round(error.retry_after, 2))
        elif isinstance(error, Union[CommandSignatureMismatch, CommandNotFound]):
            content = _("Sorry, but this command seems to be unavailable! Please try again later...")
        elif isinstance(error, CheckFailure):
            content = _("You can't use this command.")
        else:
            content = _("Sorry, but something went wrong! Please try again later...")
            if isinstance(error, CommandInvokeError):

                traceback_formatted = f"```py\n{traceback.format_exc()}\n```"

                error_title = f"{self.display_emoji} Error"
                if interaction.command:

                    _app_cmd = self.bot.get_app_command(interaction.command.qualified_name)
                    if _app_cmd is not None:
                        command = _app_cmd.mention
                    else:
                        command = f"**/{interaction.command.qualified_name}**"

                    error_title += f" in command {command}"

                embed = discord.Embed(
                    description=error_title, color=self.bot.theme.error, timestamp=interaction.created_at
                )
                embed.set_author(name=f'{interaction.user} | {interaction.user.id}', icon_url=interaction.user.avatar)
                embed.set_footer(text=f'ID: {interaction.id}')

                fp = io.BytesIO(traceback.format_exc().encode('utf-8'))
                traceback_fp = discord.File(fp, filename='traceback.py')

                if len(traceback_formatted) >= 1980:

                    paginator = WrappedPaginator(prefix='```py', suffix='```', max_size=1980)

                    result = str(traceback.format_exc())
                    if len(result) <= 2000:
                        if result.strip() == '':
                            result = "\u200b"
                    paginator.add_line(result)
                    interface = PaginatorInterface(self.bot, paginator, owner=interaction.user)

                    await self.traceback_log.send(embed=embed, file=traceback_fp)
                    await interface.send_to(self.bot.owner)
                else:
                    await self.traceback_log.send(embed=embed, file=traceback_fp)

        embed = discord.Embed(description=content, color=self.bot.theme.error)
        # timestamp = interaction.created_at
        await send_error(embed=embed, view=view)


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(ErrorHandler(bot))
