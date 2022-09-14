from typing import TYPE_CHECKING, Any, Optional, Union

import discord
from discord.app_commands import AppCommandError


class LatteAppError(AppCommandError):
    """Base class for all Latte errors."""

    def __init__(self, error, *args, **kwargs):
        super().__init__(error, *args, **kwargs)
        self.original = error


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
    pass


class TokenInvalid(LatteAPIError):
    pass


class TokenExpired(LatteAPIError):
    pass


class TokenNotFound(LatteAPIError):
    pass
