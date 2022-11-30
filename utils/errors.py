from typing import TYPE_CHECKING, Any, Optional, Union

import discord
from discord.app_commands import AppCommandError


class LatteAppError(AppCommandError):
    """Base class for all Latte errors."""

    def __init__(self, error, *args, **kwargs):
        super().__init__(error, *args)
        self.original = error
        self.view: Optional[discord.ui.View] = kwargs.pop("view", None)
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
