from __future__ import annotations

from typing import TYPE_CHECKING

from discord import Interaction, app_commands
from discord.app_commands import locale_str as _
from discord.ext import commands

if TYPE_CHECKING:
    from bot import LatteBot


class Testing(commands.Cog):
    """Bot Events"""

    def __init__(self, bot: LatteBot) -> None:
        self.bot: LatteBot = bot
        # self.ctx_user_store = app_commands.ContextMenu(
        #     name=_('ctx_test'),
        #     callback=self.ctx_test,
        #     extras=dict(cog=self),
        # )
        # self._ = bot.translator.translate
        # if i18n.bot is discord.utils.MISSING:
        #     i18n.bot = bot

    # async def ctx_test(self, interaction: Interaction, member: discord.Member):
    #     print('ctx_test')

    # @app_commands.command(name=_('test_login'), description=_('test_login_desc'))
    # @app_commands.describe(username=_('test_login_username'), password=_('test_login_password'))
    # @app_commands.rename(username=_('username'), password=_('password'))
    # async def test_login(self, interaction: Interaction, username: str, password: str) -> None:
    #
    #     msg = await interaction.translate(string="Hello World!")
    #
    #     await interaction.response.send_message(msg)

    @app_commands.command(name=_('test_choice'), description=_('test_choice_desc'))
    @app_commands.choices(
        colour=[  # param name
            app_commands.Choice(name=_("Red"), value="red"),
            app_commands.Choice(name=_("Green"), value="green"),
            app_commands.Choice(name=_("Blue"), value="blue"),
        ]
    )
    async def test_choice(self, interaction: Interaction, colour: app_commands.Choice[str]) -> None:
        """Test command"""

        await interaction.response.send_message(colour)

    test_group = app_commands.Group(name=_('test_group'), description=_('test_group_desc'))

    @test_group.command(name=_('test_group_cmd'), description=_('test_group_cmd_desc'))
    async def test_group_cmd(self, interaction: Interaction) -> None:
        """Test command"""
        await interaction.response.send_message(interaction.command.qualified_name)

    # @test_group.command(name=_('test_group_command'), description=_('test_group_command_desc'))
    # @app_commands.rename(queue=_('queue'))
    # async def test_group_command(self, interaction: Interaction, queue: str) -> None:
    #     """Test group command"""
    #
    #     msg = await interaction.translate(
    #         string="Hello World!"
    #     )
    #
    #     await interaction.response.send_message(msg)


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Testing(bot))
