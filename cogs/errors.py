from __future__ import annotations

import io
import logging
import traceback
from typing import TYPE_CHECKING, Any, Union

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

    async def on_application_command_error(self, interaction: Interaction, error: AppCommandError):
        """Handles errors for all application commands associated with this CommandTree."""

        # if isinstance(error, (discord.Forbidden, discord.NotFound)):
        #     return

        # traceback
        if self.bot.is_debug():
            traceback.print_exception(type(error), error, error.__traceback__)  # TODO: remove this when release

        async def send_error(**kwargs: Any) -> None:
            if interaction.response.is_done():
                message = await interaction.followup.send(**kwargs, ephemeral=True)
                delete_after = kwargs.get('delete_after')
                if delete_after:
                    await message.delete(delay=delete_after)
                return
            await interaction.response.send_message(**kwargs, ephemeral=True)

        view = ViewAuthor(interaction)
        delete_after = None

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
            delete_after = error.delete_after
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
            if self.bot.traceback_log is not None:
                if isinstance(error, CommandInvokeError):

                    traceback_formatted = f"```py\n{traceback.format_exc()}\n```"

                    embed = discord.Embed(color=self.bot.theme.error, timestamp=interaction.created_at)
                    if interaction.command:

                        app_cmd = self.bot.get_app_command(interaction.command.qualified_name)
                        embed.description = 'app command: {command}'.format(
                            command=app_cmd.mention if app_cmd else f"**/{interaction.command.qualified_name}**"
                        )

                    embed.set_author(
                        name=f'{interaction.user} | {interaction.user.id}', icon_url=interaction.user.avatar
                    )
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
                        interface = PaginatorInterface(
                            self.bot, paginator, owner=interaction.user, emoji=self.display_emoji
                        )

                        await self.bot.traceback_log.send(embed=embed, file=traceback_fp)
                        await interface.send_to(self.bot.owner)
                    else:
                        await self.bot.traceback_log.send(embed=embed, file=traceback_fp)

        embed = discord.Embed(
            description=content,
            color=self.bot.theme.error,
        )
        await send_error(embed=embed, view=view, delete_after=(delete_after or 120.0))


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(ErrorHandler(bot))
