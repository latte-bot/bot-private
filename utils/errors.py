from typing import Optional

import discord
from discord.app_commands import AppCommandError


class LatteAppError(AppCommandError):
    """Base class for all Latte errors."""

    def __init__(self, error, *args, **kwargs):
        super().__init__(error, *args)
        self.original = error
        self.view: Optional[discord.ui.View] = kwargs.pop("view", None)
        self.ephemeral: bool = kwargs.pop("ephemeral", True)
        self.extras = kwargs


class CommandError(LatteAppError):
    """Base class for all Latte app command errors."""

    pass


class BadArgument(LatteAppError):
    """Raised when a command is called with invalid arguments."""

    pass


class CommandNotFound(LatteAppError):
    """Raised when a command is not found."""

    pass


class CheckFailure(LatteAppError):
    """Raised when a check fails."""

    pass


class CommandInvokeError(LatteAppError):
    """Raised when a command invoke fails."""

    pass


class CommandOnCooldown(LatteAppError):
    """Raised when a command is on cooldown."""

    pass


class UserNotFound(LatteAppError):
    """Raised when a user is not found."""

    pass


class NotInDatabase(LatteAppError):
    """Raised when a user is not found."""

    pass


class EmptyDatabase(LatteAppError):
    """Raised when a user is not found."""

    pass


class NotOwner(LatteAppError):
    """Raised when a user is not found."""

    pass


class LatteAPIError(AppCommandError):
    """Base class for all Latte API errors."""

    pass


class TokenInvalid(LatteAPIError):
    """Raised when a token is invalid."""

    pass


class TokenExpired(LatteAPIError):
    """Raised when a token is expired."""

    pass


class TokenNotFound(LatteAPIError):
    """Raised when a token is not found."""

    pass


class ButtonOnCooldown(Exception):
    """Raised when a button is on cooldown."""

    def __init__(self, cooldown: discord.app_commands.Cooldown) -> None:
        self.cooldown: discord.app_commands.Cooldown = cooldown
        self.retry_after: float = cooldown.get_retry_after()
        super().__init__(f'You are on cooldown. Try again in {self.retry_after:.2f}s')


# if isinstance(error, app_commands.errors.CheckFailure):
#     return
# user_locale = await get_user_locale(i.user.id, i.client.db)
# if hasattr(e, "code") and e.code in [10062, 10008, 10015]:
#     embed = error_embed(message=text_map.get(624, i.locale, user_locale))
#     embed.set_author(name=text_map.get(623, i.locale, user_locale))
# else:
#     log.warning(f"[{i.user.id}]{type(e)}: {e}")
#     # print traceback
#     if i.client.debug:
#         log.warning(traceback.format_exc())
#     sentry_sdk.capture_exception(e)
#     embed = error_embed(message=text_map.get(513, i.locale, user_locale))
#     if embed.description is not None:
#         embed.description += f"\n\n```{e}```"
#     embed.set_author(
#         name=text_map.get(135, i.locale, user_locale),
#         icon_url=i.user.display_avatar.url,
#     )
#     embed.set_thumbnail(url="https://i.imgur.com/Xi51hSe.gif")
# view = discord.ui.View()
# view.add_item(
#     discord.ui.Button(
#         label=text_map.get(642, i.locale, user_locale),
#         url="https://discord.gg/ryfamUykRw",
#         emoji="<:discord_icon:1032123254103621632>",
#     )
# )
#
# try:
#     await i.response.send_message(
#         embed=embed,
#         ephemeral=True,
#         view=view,
#     )
# except discord.errors.InteractionResponded:
#     await i.followup.send(
#         embed=embed,
#         ephemeral=True,
#         view=view,
#     )
# except discord.errors.NotFound:
#     pass
