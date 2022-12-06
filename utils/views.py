from __future__ import annotations

import io
import logging
import time
import traceback
from typing import TYPE_CHECKING, Any, List, Optional, Type, Union

import discord
import valorantx
from discord import Interaction, ui
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

from .chat_formatting import bold
from .errors import ButtonOnCooldown, CheckFailure, LatteAppError
from .i18n import _
from .useful import LatteEmbed

if TYPE_CHECKING:
    from discord import Client, InteractionMessage, Message
    from typing_extensions import Self

    from bot import LatteBot

    ClientBot = Union[Client, LatteBot]


_log = logging.getLogger(__name__)


def key(interaction: discord.Interaction) -> Union[discord.User, discord.Member]:
    return interaction.user


class Button(ui.Button):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# thanks stella_bot # https://github.com/InterStella0/stella_bot/blob/master/utils/buttons.py
class BaseView(ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._message: Optional[Union[Message, InteractionMessage]] = None

    def reset_timeout(self) -> None:
        self.timeout = self.timeout

    async def _scheduled_task(self, item: ui.Item, interaction: Interaction):
        try:
            item._refresh_state(interaction, interaction.data)  # type: ignore

            allow = await self.interaction_check(interaction)
            if not allow:
                return await self.on_check_failure(interaction)

            if self.timeout:
                self.__timeout_expiry = time.monotonic() + self.timeout

            # if not interaction.response.type:
            #   await interaction.response.defer()

            await item.callback(interaction)
        except Exception as e:
            return await self.on_error(interaction, e, item)

    async def on_error(self, interaction: Interaction, error: Exception, item: ui.Item[Any]) -> None:

        # cooldown message
        if isinstance(error, ButtonOnCooldown):
            if isinstance(item, ui.Button):
                msg = _("This button is on cooldown. Try again in {time}.").format(
                    time=bold(str(round(error.retry_after, 2)))
                )
            elif isinstance(item, ui.Select):
                msg = _("This select is on cooldown. Try again in {time}.").format(
                    time=bold(str(round(error.retry_after, 2)))
                )
            else:
                msg = _("You are on cooldown. Try again in {time}.").format(time=bold(str(round(error.retry_after, 2))))
        else:
            msg = getattr(error, 'original', _("An error occurred while processing this interaction."))

        embed = LatteEmbed.to_error(
            description=msg,
        )

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

        _log.exception(error)

    # --- code from pycord ---

    async def on_check_failure(self, interaction: Interaction) -> None:
        """coro

        A callback that is called when the interaction check fails.

        Parameters
        ----------
        interaction: Interaction
            The interaction that failed the check.
        """
        pass

    def disable_all_items(self, *, exclusions: Optional[List[ui.Item]] = None) -> Self:
        """
        Disables all items in the view.

        Parameters
        ----------
        exclusions: Optional[List[ui.Item]]
            A list of items in `self.children` to not disable from the view.
        """
        for child in self.children:
            if exclusions is not None or child not in exclusions:
                child.disabled = True
        return self

    def enable_all_items(self, *, exclusions: Optional[List[ui.Item]] = None) -> Self:
        """
        Enables all items in the view.

        Parameters
        ----------
        exclusions: Optional[List[ui.Item]]
            A list of items in `self.children` to not enable from the view.
        """
        for child in self.children:
            if exclusions is not None or child not in exclusions:
                child.disabled = False
        return self

    # --- end of code from pycord ---

    def disable_items(self, cls: Optional[Type[ui.Item]] = None) -> Self:
        for item in self.children:
            if cls is not None:
                if isinstance(item, cls):
                    item.disabled = True
        return self

    def remove_item_by_type(self, *, cls: Optional[Type[ui.Item]] = None) -> Self:
        for item in self.children:
            if cls is not None:
                if isinstance(item, cls):
                    self.remove_item(item)
        return self

    def disable_buttons(self) -> Self:
        return self.disable_items(ui.Button)

    def disable_selects(self) -> Self:
        return self.disable_items(ui.Select)

    @property
    def message(self) -> Optional[Union[Message, InteractionMessage]]:
        return self._message

    @message.setter
    def message(self, value: Optional[Union[Message, InteractionMessage]]) -> None:
        self._message = value


# thanks stella_bot
class ViewAuthor(BaseView):
    def __init__(self, interaction: Interaction, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.interaction = interaction
        self.bot: ClientBot = interaction.client
        self.is_command = interaction.command is not None
        self.cooldown = commands.CooldownMapping.from_cooldown(3.0, 10.0, key)
        self.cooldown_user = commands.CooldownMapping.from_cooldown(1.0, 8.0, key)

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Only allowing the context author to interact with the view"""

        author = self.interaction.user
        user = interaction.user

        if await self.bot.is_owner(user):
            return True

        if isinstance(user, discord.Member) and user.guild_permissions.administrator:
            return True

        if user != author:
            return False

        bucket = self.cooldown.get_bucket(interaction)
        if bucket is not None:
            if bucket.update_rate_limit():
                raise ButtonOnCooldown(bucket)

        return True

    async def on_check_failure(self, interaction: Interaction) -> None:
        """Handles the error when the check fails"""

        author = self.interaction.user

        bucket_user = self.cooldown_user.get_bucket(interaction)
        if bucket_user is not None:
            if bucket_user.update_rate_limit():
                raise ButtonOnCooldown(bucket_user)

        if self.interaction.command is not None:
            command_name: str = self.interaction.command.qualified_name
            get_app_cmd = self.bot.get_app_command(command_name)

            if get_app_cmd is not None:
                app_cmd = f'{get_app_cmd.mention}'
            else:
                app_cmd = f'/`{command_name}`'

            content = _("Only {author} can use this. If you want to use it, use {app_cmd}").format(
                author=author.mention, app_cmd=app_cmd
            )
        else:
            content = _("Only `{author}` can use this.").format(author=author.mention)

        raise CheckFailure(content)


# TODO: URL View


# class LatteOnError:
#
#     def __inti__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#     async def send_trace_back(self):
#         ...
#
#     async def send_message_error(self):
#         ...

# async def send_traceback(interaction: discord.Interaction, error: Union[Exception, discord.app_commands.AppCommandError]) -> None:
#          if isinstance(error, CommandInvokeError):
#
#             traceback_formatted = f"```py\n{traceback.format_exc()}\n```"
#
#             error_title = f"{self.display_emoji} Error"
#             if interaction.command:
#
#                 _app_cmd = self.bot.get_app_command(interaction.command.qualified_name)
#                 if _app_cmd is not None:
#                     command = _app_cmd.mention
#                 else:
#                     command = f"**/{interaction.command.qualified_name}**"
#
#                 error_title += f" in command {command}"
#
#             embed = discord.Embed(
#                 description=error_title, color=interaction.client.theme.error,  # type: ignore
#                 timestamp=interaction.created_at
#             )
#             embed.set_author(
#                 name=f'{interaction.user} | {interaction.user.id}',
#                 icon_url=interaction.user.avatar
#             )
#             embed.set_footer(text=f'ID: {interaction.id}')
#
#             if len(traceback_formatted) >= 1980:
#
#                 paginator = WrappedPaginator(prefix='```py', suffix='```', max_size=1980)
#
#                 result = str(traceback.format_exc())
#                 if len(result) <= 2000:
#                     if result.strip() == '':
#                         result = "\u200b"
#                 paginator.add_line(result)
#                 interface = PaginatorInterface(interaction.client, paginator, owner=interaction.user)  # type: ignore
#
#                 await interface.send_to(interaction.client.owner)  # type: ignore


async def latte_error_handler(interaction: discord.Interaction, error: Union[Exception, AppCommandError]):

    if isinstance(error, (discord.Forbidden, discord.NotFound, discord.HTTPException)):
        return

    if interaction.client.is_debug():  # type: ignore
        _log.warning(traceback.format_exc().encode('utf-8'))
        fp = io.BytesIO(traceback.format_exc().encode('utf-8'))
        traceback_fp = discord.File(fp, filename='traceback.py')
        await interaction.client.traceback_log.send(file=traceback_fp)  # type: ignore

    async def send_message(*args: Any, **kwargs: Any) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(*args, **kwargs, ephemeral=True)
        else:
            await interaction.response.send_message(*args, **kwargs, ephemeral=True)

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
    elif isinstance(error, CommandSignatureMismatch):
        content = _("Sorry, but this command seems to be unavailable! Please try again later...")
    elif isinstance(error, CheckFailure):
        content = _("You can't use this command.")
    else:
        content = _("Sorry, but something went wrong! Please try again later...")

    embed = discord.Embed(description=content, color=interaction.client.theme.error)  # type: ignore
    view = ...
    await send_message(embed=embed, view=view)
