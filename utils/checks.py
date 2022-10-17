from typing import Optional

import discord
from discord import Interaction, app_commands

__all__ = ('owner_only', 'cooldown_5s', 'cooldown_10s', 'custom_cooldown')


def owner_only() -> app_commands.check:
    async def actual_check(interaction: Interaction):
        return await interaction.client.is_owner(interaction.user)  # type: ignore

    return app_commands.check(actual_check)


def cooldown_5s(interaction: discord.Interaction) -> Optional[app_commands.Cooldown]:
    if interaction.user == interaction.client.owner:  # type: ignore
        return None
    return app_commands.Cooldown(1, 5)


def cooldown_10s(interaction: discord.Interaction) -> Optional[app_commands.Cooldown]:
    if interaction.user == interaction.client.owner:  # type: ignore
        return None
    return app_commands.Cooldown(1, 10)


def custom_cooldown(interaction: discord.Interaction, seconds: int) -> Optional[app_commands.Cooldown]:
    if interaction.user == interaction.client.owner:  # type: ignore
        return None
    return app_commands.Cooldown(1, seconds)
