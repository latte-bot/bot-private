from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, TypeAlias, Union

import discord
from discord import AppCommandType, Interaction, app_commands, ui

# i18n
from discord.app_commands import (  # ContextMenu as AppContextMenu,
    AppCommand as AppCommandBase,
    AppCommandGroup as AppCommandGroupBase,
    Command as AppCommand,
    Group as AppCommandGroup,
    locale_str as _T,
)
from discord.app_commands.checks import dynamic_cooldown
from discord.ext import commands

from utils.checks import cooldown_5s
from utils.errors import CommandError
from utils.useful import LatteCDN
from utils.views import ViewAuthor

if TYPE_CHECKING:
    from discord import Client

    from bot import LatteBot

    ClientBot: TypeAlias = Union[Client, LatteBot]

    AppCommandType: TypeAlias = Union[AppCommand, AppCommandGroup]
    AppCommandEntry: TypeAlias = Dict[Any, List[AppCommandType]]

MISSING = discord.utils.MISSING

IGNORE_EXTENSIONS = ['Admin', 'Events', 'Help', 'Jishaku']


@lru_cache(maxsize=1)
def front_help_command_embed(interaction: Interaction) -> discord.Embed:
    embed = discord.Embed(
        colour=interaction.client.theme.secondary,  # type: ignore
    )
    embed.set_author(
        name='{bot} - Help'.format(bot=interaction.client.user.display_name),
        icon_url=interaction.client.user.display_avatar,
    )
    embed.set_image(url=str(LatteCDN.help_banner))
    return embed


class CogButton(ui.Button['HelpView']):
    def __init__(self, cog: commands.Cog, *args, **kwargs) -> None:
        self.cog = cog
        emoji = getattr(cog, 'display_emoji', None)
        super().__init__(emoji=emoji, *args, **kwargs)

    async def callback(self, interaction: Interaction) -> None:
        assert self.view is not None

        if self.view.current_cog == self.cog:
            return

        self.view.current_cog = self.cog

        self.view.embeds = self.view.cog_pages.get(self.cog)
        await self.view.show_page(interaction, 0)


class HelpView(ViewAuthor):
    def __init__(self, interaction: Interaction, help_command: HelpCommand) -> None:
        self.interaction: Interaction = interaction
        self.help_command: HelpCommand = help_command
        self.bot: ClientBot = interaction.client
        super().__init__(interaction=interaction, timeout=120)
        self.current_page: int = 0
        self.embeds: List[discord.Embed] = []
        self.cog_pages: Dict[commands.Cog, List[discord.Embed]] = {}
        self.current_cog: commands.Cog = MISSING
        self.after_select: bool = True
        self.cooldown = commands.CooldownMapping.from_cooldown(1, 3, lambda inter: inter.user)
        self.clear_items()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await super().interaction_check(interaction)

    async def on_timeout(self) -> None:
        self.clear_items()
        self.add_item(ui.Button(label='ꜱᴜᴘᴘᴏʀᴛ ꜱᴇʀᴠᴇʀ', url=self.bot.support_invite_url))  # emoji=str(support_emoji)
        self.add_item(ui.Button(label='ɪɴᴠɪᴛᴇ ᴍᴇ', url=self.bot.invite_url))  # emoji=str(latte_emoji)
        await self.interaction.edit_original_response(view=self)

    @ui.button(label='≪', row=1)
    async def first_page(self, interaction: Interaction, button: ui.Button):
        await self.show_page(interaction, 0)

    @ui.button(label="Back", style=discord.ButtonStyle.blurple, row=1)
    async def back_page(self, interaction: Interaction, button: ui.Button):
        await self.show_page(interaction, -1)

    @ui.button(label="Next", style=discord.ButtonStyle.blurple, row=1)
    async def next_page(self, interaction: Interaction, button: ui.Button):
        await self.show_page(interaction, +1)

    @ui.button(label='≫', row=1)
    async def last_page(self, interaction: Interaction, button: ui.Button):
        await self.show_page(interaction, len(self.embeds) - 1)

    def _update_buttons(self) -> None:
        nav_buttons = [self.first_page, self.back_page, self.next_page, self.last_page]

        if self.after_select and len(self.embeds) > 1:
            for button in nav_buttons:
                self.add_item(button)
            self.after_select = False
        elif not self.after_select and len(self.embeds) == 1:
            for button in nav_buttons:
                self.remove_item(button)
            self.after_select = True

        page = self.current_page
        total = len(self.embeds) - 1
        self.next_page.disabled = page == total
        self.back_page.disabled = page == 0
        self.first_page.disabled = page == 0
        self.last_page.disabled = page == total

    async def show_page(self, interaction: Interaction, page_number: int) -> None:
        try:
            if page_number <= 1 and page_number != 0:
                page_number = self.current_page + page_number
            self.current_page = page_number
            self._update_buttons()
            embeds = self.embeds[self.current_page]
            await interaction.response.edit_message(embed=embeds, view=self, attachments=[])
        except (IndexError, ValueError):
            return

    async def start(self) -> None:

        mapping = self.help_command.get_cog_app_command_mapping()

        for cog, command in sorted(mapping.items(), key=lambda x: x[0].qualified_name):
            if not command:
                continue
            self.add_item(CogButton(cog=cog))
            self.cog_pages[cog] = await self.help_command.help_command_embed(cog)

        embed = front_help_command_embed(self.interaction)
        await self.interaction.response.send_message(embed=embed, view=self)


class HelpCommand:
    def __init__(self, interaction: Interaction) -> None:
        self.bot: ClientBot = interaction.client
        self.interaction = interaction

    def help_embed_template(self, cog: commands.Cog) -> discord.Embed:
        emoji = getattr(cog, 'display_emoji', '')
        embed = discord.Embed(
            title=f"{emoji} {cog.qualified_name}",
            color=self.bot.theme.primacy,
            description=cog.description + '\n' or "No description provided" + '\n',
        )
        return embed

    async def help_command_embed(self, cog: commands.Cog) -> List[discord.Embed]:

        all_app_commands = await self.get_app_command_from_cog(list(cog.walk_app_commands()))

        embeds = []
        embed = self.help_embed_template(cog)

        for command in sorted(
            all_app_commands, key=lambda c: c.qualified_name if isinstance(c, AppCommandGroupBase) else c.name
        ):

            command_des = command.description.lower().split(" | ")
            index = 1 if self.interaction.locale != discord.Locale.thai and len(command_des) > 1 else 0

            embed.description += f'\n{command.mention} - {command_des[index]}'

            if len(embed.description.splitlines()) == 8:
                embeds.append(embed)
                embed = self.help_embed_template(cog)

        if len(embed.description.splitlines()) > 1:
            embeds.append(embed)

        return embeds

    def get_cog_app_command_mapping(
        self,
    ) -> Mapping[commands.Cog, List[Union[AppCommandGroup, AppCommand[Any, ..., Any]]]]:
        mapping = {
            cog: sorted(cog.__cog_app_commands__, key=lambda c: c.qualified_name)
            for cog in sorted(self.bot.cogs.values(), key=lambda c: c.qualified_name)
            if cog.__cog_app_commands__ and cog.qualified_name not in IGNORE_EXTENSIONS
        }
        return mapping

    async def get_app_command_from_cog(self, app_command_entry: List[AppCommandType]) -> List[Any]:

        app_command_list = []

        fetch_app_command: List[AppCommandBase] = await self.bot.fetch_app_commands()

        for app in app_command_entry:
            for fetch in fetch_app_command:
                if fetch.type == discord.AppCommandType.chat_input:
                    if app.qualified_name.lower() == fetch.name.lower():
                        if len(fetch.options) > 0:
                            # app_command_list.append(fetch)
                            for option in fetch.options:
                                if isinstance(option, AppCommandGroupBase):
                                    app_command_list.append(option)
                        else:
                            app_command_list.append(fetch)

        return app_command_list

    async def help_command_error(self, error: str) -> None:
        raise CommandError(error)

    async def callback(self) -> None:
        view = HelpView(self.interaction, self)
        await view.start()


class Help(commands.Cog):
    """Help command"""

    def __init__(self, bot: LatteBot):
        self.bot: LatteBot = bot

    @app_commands.command(name=_T('help'))
    @dynamic_cooldown(cooldown_5s)
    async def help_command(self, interaction: Interaction):
        """Help command"""
        help_command = HelpCommand(interaction)
        await help_command.callback()


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Help(bot))
