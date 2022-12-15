from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Union

import discord
from discord import AppCommandType, Interaction, app_commands, ui
from discord.app_commands import locale_str as _T
from discord.app_commands.checks import dynamic_cooldown
from discord.ext import commands

# utils
from utils.checks import cooldown_5s
from utils.i18n import _
from utils.pages import LattePages, ListPageSource
from utils.views import ViewAuthor

if TYPE_CHECKING:
    from discord import Client

    from bot import LatteBot

    ClientBot = Union[Client, LatteBot]
    AppCommandType = Union[app_commands.Command, app_commands.Group]


class HelpPageSource(ListPageSource):
    def __init(self, source: List[app_commands.AppCommand]) -> None:
        super().__init__(source, per_page=6)

    @staticmethod
    def default(cog: commands.Cog) -> discord.Embed:
        emoji = getattr(cog, 'display_emoji', '')
        bot = getattr(cog, 'bot', None)
        embed = discord.Embed(
            title=f"{emoji} {cog.qualified_name}",
            description=cog.description + '\n' or _('No description provided') + '\n',
        )
        if bot is not None:
            embed.colour = bot.theme.primacy
        return embed

    def format_page(self, menu: Any, entries: List[app_commands.AppCommand]) -> discord.Embed:
        embed = self.default(menu.current_cog)

        for command in sorted(
            entries, key=lambda c: c.qualified_name if isinstance(c, app_commands.AppCommandGroup) else c.name
        ):
            command_des = command.description.lower().split(" | ")
            index = 1 if menu.interaction.locale != discord.Locale.thai and len(command_des) > 1 else 0

            embed.description += f'\n{command.mention} - {command_des[index]}'

        return embed


def front_help_command_embed(bot: ClientBot) -> discord.Embed:
    embed = discord.Embed(colour=bot.theme.secondary)
    embed.set_author(
        name='{display_name} - Help'.format(display_name=bot.user.display_name),
        icon_url=bot.user.display_avatar,
    )
    embed.set_image(url=str(bot.l_cdn.help_banner))
    return embed


class CogButton(ui.Button['HelpCommand']):
    def __init__(self, cog: commands.Cog, *args, **kwargs) -> None:
        self.cog = cog
        emoji = getattr(cog, 'display_emoji')
        super().__init__(emoji=emoji, style=discord.ButtonStyle.primary, *args, **kwargs)
        if self.emoji is None:
            self.label = cog.qualified_name

    def get_cog_app_commands(self, cog_app_commands: List[AppCommandType]) -> List[app_commands.AppCommand]:
        fetch_app_commands = self.view.bot.get_app_commands()
        app_command_list = []
        for c_app in cog_app_commands:
            for f_app in fetch_app_commands:
                if f_app.type == discord.AppCommandType.chat_input:
                    if c_app.qualified_name.lower() == f_app.name.lower():
                        if [option for option in f_app.options if isinstance(option, app_commands.Argument)] or (
                            not len(f_app.options)
                        ):
                            app_command_list.append(f_app)
                        for option in f_app.options:
                            if isinstance(option, app_commands.AppCommandGroup):
                                app_command_list.append(option)

        return app_command_list

    async def callback(self, interaction: Interaction) -> None:
        assert self.view is not None

        self.view.current_cog = self.cog
        self.view.source = HelpPageSource(self.get_cog_app_commands(list(self.cog.walk_app_commands())), per_page=6)

        max_pages = self.view.get_max_pages()
        if max_pages is not None and max_pages > 1:
            self.view.add_nav_buttons()
        else:
            self.view.remove_nav_buttons()
        self.view.home_button.disabled = False
        await self.view.show_page(interaction, 0)

    # def test(self, cog_app_commands: List[AppCommandType]) -> List[Any]:
    #     fetch_app_commands = self.view.bot.get_app_commands()
    #     app_command_list = [
    #         f_app
    #         for c_app in cog_app_commands
    #         for f_app in fetch_app_commands
    #         if f_app.type == discord.AppCommandType.chat_input
    #         if c_app.qualified_name.lower() == f_app.name.lower()
    #         # if [option for option in f_app.options if isinstance(option, app_commands.Argument)] or (not len(f_app.options))
    #         for option in f_app.options
    #         if isinstance(option, app_commands.AppCommandGroup)
    #     ]
    #     return app_command_list


class HelpCommand(ViewAuthor, LattePages):
    def __init__(self, interaction: Interaction, cogs: List[str]) -> None:
        super().__init__(interaction, timeout=600.0)
        self.cogs = cogs
        self.current_cog: Optional[commands.Cog] = None
        self.first_page.row = self.previous_page.row = self.next_page.row = self.last_page.row = 1
        self.embed: Optional[discord.Embed] = front_help_command_embed(self.bot)
        self.home_button.emoji = self.bot.l_emoji.latte_icon
        self.clear_items()

    @ui.button(emoji='🏘️', style=discord.ButtonStyle.primary, disabled=True)
    async def home_button(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        self.home_button.disabled = True
        self.remove_nav_buttons()
        await self.message.edit(embed=self.embed, view=self)

    def add_nav_buttons(self) -> None:
        self.add_item(self.first_page)  # type: ignore
        self.add_item(self.previous_page)  # type: ignore
        self.add_item(self.next_page)  # type: ignore
        self.add_item(self.last_page)  # type: ignore

    def remove_nav_buttons(self) -> None:
        self.remove_item(self.first_page)  # type: ignore
        self.remove_item(self.previous_page)  # type: ignore
        self.remove_item(self.next_page)  # type: ignore
        self.remove_item(self.last_page)  # type: ignore

    def add_cog_buttons(self) -> None:
        for cog in sorted(self.bot.cogs.values(), key=lambda c: c.qualified_name):
            if cog.qualified_name not in self.cogs or len(list(cog.walk_app_commands())) <= 0:
                continue
            self.add_item(CogButton(cog=cog))

    async def callback(self) -> None:

        self.add_item(self.home_button)
        self.add_cog_buttons()
        await self.interaction.response.send_message(embed=self.embed, view=self)

        self.message = await self.interaction.original_response()


class Help(commands.Cog):
    """Help command"""

    def __init__(self, bot: LatteBot):
        self.bot: LatteBot = bot

    @app_commands.command(name=_T('help'), description=_T('help command'))
    @dynamic_cooldown(cooldown_5s)
    async def help_command(self, interaction: Interaction):
        cogs = ['About', 'Valorant']
        help_command = HelpCommand(interaction, cogs)
        await help_command.callback()


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Help(bot))
