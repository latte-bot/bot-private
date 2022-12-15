from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import discord
from discord import AppCommandType, Interaction, app_commands, ui
from discord.app_commands import (  # ContextMenu as AppContextMenu,
    AppCommandGroup as AppCommandGroupBase,
    Command as AppCommand,
    Group as AppCommandGroup,
    locale_str as _T,
)
from discord.app_commands.checks import dynamic_cooldown
from discord.ext import commands

# utils
from utils.checks import cooldown_5s
from utils.i18n import _
from utils.pages import LattePages, ListPageSource
from utils.useful import LatteCDN
from utils.views import ViewAuthor

if TYPE_CHECKING:
    from discord import Client

    from bot import LatteBot

    ClientBot = Union[Client, LatteBot]
    AppCommandType = Union[AppCommand, AppCommandGroup]
    AppCommandEntry = Dict[Any, List[AppCommandType]]

MISSING = discord.utils.MISSING

ONLY_EXTENSIONS = ['About', 'Valorant']


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
            entries, key=lambda c: c.qualified_name if isinstance(c, AppCommandGroupBase) else c.name
        ):
            command_des = command.description.lower().split(" | ")
            index = 1 if menu.interaction.locale != discord.Locale.thai and len(command_des) > 1 else 0

            embed.description += f'\n{command.mention} - {command_des[index]}'

        return embed


@lru_cache(maxsize=1)
def front_help_command_embed(interaction: Interaction) -> discord.Embed:
    embed = discord.Embed(colour=interaction.client.theme.secondary)  # type: ignore
    embed.set_author(
        name='{display_name} - Help'.format(display_name=interaction.client.user.display_name),
        icon_url=interaction.client.user.display_avatar,
    )
    embed.set_image(url=str(LatteCDN.help_banner))
    return embed


class CogButton(ui.Button['HelpCommand']):
    def __init__(self, cog: commands.Cog, *args, **kwargs) -> None:
        self.cog = cog
        emoji = getattr(cog, 'display_emoji', None)
        if emoji is None:
            self.label = cog.qualified_name
        super().__init__(emoji=emoji, *args, **kwargs)

    def get_cog_app_commands(self, cog_app_commands: List[AppCommandType]) -> List[Any]:

        fetch_app_commands = self.view.bot.get_app_commands()
        app_command_list = []
        for c_app in cog_app_commands:
            for f_app in fetch_app_commands:
                if f_app.type == discord.AppCommandType.chat_input:
                    if c_app.qualified_name.lower() == f_app.name.lower():
                        if len(f_app.options) > 0:
                            any_option = any(
                                [option for option in f_app.options if isinstance(option, app_commands.AppCommandGroup)]
                            )
                            if not any_option:
                                app_command_list.append(f_app)
                            for option in f_app.options:
                                if isinstance(option, app_commands.AppCommandGroup):
                                    app_command_list.append(option)
                        else:
                            app_command_list.append(f_app)

        return app_command_list

    # def test(self, cog_app_commands: List[AppCommandType]) -> List[Any]:
    #     fetch_app_commands = self.view.bot.get_app_commands()
    #     app_command_list = [
    #         f_app
    #         for c_app in cog_app_commands
    #         for f_app in fetch_app_commands
    #         if f_app.type == discord.AppCommandType.chat_input
    #         if c_app.qualified_name.lower() == f_app.name.lower()
    #         if isinstance(f_app, app_commands.AppCommand)
    #     ]
    #     return app_command_list

    async def callback(self, interaction: Interaction) -> None:
        assert self.view is not None

        self.view.current_cog = self.cog
        self.view.source = HelpPageSource(self.get_cog_app_commands(list(self.cog.walk_app_commands())), per_page=6)

        max_pages = self.view.get_max_pages()
        if max_pages is not None and max_pages > 1:
            self.view.add_nav_buttons()
        else:
            self.view.remove_nav_buttons()

        await self.view.show_page(interaction, 0)


class CogPages(LattePages):
    def __init__(self, *, p_interaction: Interaction) -> None:
        super().__init__(p_interaction, timeout=600.0)
        self.current_cog: Optional[commands.Cog] = None


class HelpCommand(ViewAuthor, CogPages):
    def __init__(self, interaction: Interaction) -> None:
        super().__init__(interaction, p_interaction=interaction)
        self.clear_items()
        self.current_cog: Optional[commands.Cog] = None
        self.cog_app_commands: Dict[commands.Cog, List[discord.Embed]] = {}
        self.first_page.row = self.previous_page.row = self.next_page.row = self.last_page.row = 1

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
            if cog.qualified_name not in ONLY_EXTENSIONS:
                continue
            if not len(list(cog.walk_app_commands())) >= 0:
                continue
            self.add_item(CogButton(cog=cog))

    async def callback(self) -> None:

        self.add_cog_buttons()
        embed = front_help_command_embed(self.interaction)
        await self.interaction.response.send_message(embed=embed, view=self)

        self.message = await self.interaction.original_response()


class Help(commands.Cog):
    """Help command"""

    def __init__(self, bot: LatteBot):
        self.bot: LatteBot = bot

    @app_commands.command(name=_T('help'), description=_T('help command'))
    @dynamic_cooldown(cooldown_5s)
    async def help_command(self, interaction: Interaction):
        help_command = HelpCommand(interaction)
        await help_command.callback()


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Help(bot))
