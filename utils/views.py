from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, List, Optional, Union

import discord
from discord import Interaction, ui
from discord.ext import commands

from .chat_formatting import bold
from .errors import ButtonOnCooldown, CheckFailure
from .i18n import _
from .useful import LatteEmbed

if TYPE_CHECKING:
    from discord import InteractionMessage, Message


_log = logging.getLogger(__name__)


def key(interaction: discord.Interaction) -> Union[discord.User, discord.Member]:
    return interaction.user


class Button(ui.Button):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# thanks stella_bot
class BaseView(ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._message: Optional[Union[Message, InteractionMessage]] = None

    def reset_timeout(self) -> None:
        self.timeout = self.timeout

    # async def _scheduled_task(self, item: discord.ui.item, interaction: discord.Interaction):
    #     try:
    #
    #         item._refresh_state(interaction, interaction.data)
    #
    #         allow = await self.interaction_check(interaction)
    #         if not allow:
    #             return
    #
    #         if self.timeout:
    #             self.__timeout_expiry = time.monotonic() + self.timeout
    #
    #         await item.callback(interaction)
    #
    #         # if not interaction.response._response_type:
    #         #     await interaction.response.defer()
    #
    #     except Exception as e:
    #         return await self.on_error(interaction, e, item)

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

    def disable_all_items(self, *, exclusions: Optional[List[ui.Item]] = None) -> None:
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

    def enable_all_items(self, *, exclusions: Optional[List[ui.Item]] = None) -> None:
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
        self.is_command = interaction.command is not None
        self.cooldown = commands.CooldownMapping.from_cooldown(3.0, 10.0, key)
        self.cooldown_user = commands.CooldownMapping.from_cooldown(1.0, 8.0, key)

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Only allowing the context author to interact with the view"""

        author = self.interaction.user
        user = interaction.user

        if await self.interaction.client.is_owner(user):  # type: ignore
            return True

        if isinstance(user, discord.Member) and user.guild_permissions.administrator:
            return True

        if user != author:

            bucket_user = self.cooldown_user.get_bucket(interaction)
            if bucket_user is not None:
                if bucket_user.update_rate_limit():
                    raise ButtonOnCooldown(bucket_user)

            if self.interaction.command is not None:
                command_name: str = self.interaction.command.qualified_name
                get_app_cmd = self.interaction.client.get_app_command(command_name)  # type: ignore

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

        bucket = self.cooldown.get_bucket(interaction)
        if bucket is not None:
            if bucket.update_rate_limit():
                raise ButtonOnCooldown(bucket)

        return True


# TODO: URL View
