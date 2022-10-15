from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import Interaction, app_commands
from discord.ext import commands
from patchnote import PatchNote

if TYPE_CHECKING:
    from bot import LatteBot


class Testing(commands.Cog):
    """Bot Events"""

    def __init__(self, bot: LatteBot) -> None:
        self.bot: LatteBot = bot

    @app_commands.command()
    async def test_command(self, interaction: Interaction) -> None:
        """Test command"""
        await interaction.response.send_message("Hello World!")


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Testing(bot))
