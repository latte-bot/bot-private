from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Literal

import discord
from discord import Interaction, app_commands
from discord.app_commands import locale_str as _T
from discord.ext import commands

from utils.chat_formatting import bold, inline
from utils.checks import owner_only
from utils.errors import CommandError

if TYPE_CHECKING:
    from bot import LatteBot

_log = logging.getLogger(__file__)

# fmt: off
initial_extensions = Literal[
    'cogs.events',
    'cogs.errors',
    'cogs.help',
    'cogs.jishaku',
    'cogs.info',
    'cogs.valorant'
]
# fmt: on


class Developers(commands.Cog):
    """Developers commands"""

    def __init__(self, bot: LatteBot) -> None:
        self.bot = bot

    latte_log = app_commands.Group(
        name="_log",
        description="latte bot personal commands",
        default_permissions=discord.Permissions(
            administrator=True,
        ),
    )

    @latte_log.command(name=_T('read'), description=_T('Read the log'))
    @app_commands.describe(to_file=_T('send the log file as a file'))
    @app_commands.rename(to_file=_T('to_file'))
    @owner_only()
    async def latte_log_read(self, interaction: discord.Interaction, to_file: bool = False) -> None:
        await interaction.response.defer(ephemeral=True)
        if not to_file:
            ctx = await commands.Context.from_interaction(interaction)
            jsk = self.bot.get_command('jishaku cat')

            await jsk(ctx, '_lattebot.log')
        else:
            with open('_lattebot.log', 'r+', encoding="utf-8") as f:
                fp = io.BytesIO(f.read().encode('utf-8'))
                await interaction.followup.send(file=discord.File(fp, 'lattebot.log'))

    @latte_log.command(name=_T('clear'), description=_T('Clear the log'))
    @owner_only()
    async def latte_log_clear(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        with open('_lattebot.log', mode='r+', encoding='utf-8') as f:
            fp = io.BytesIO(f.read().encode('utf-8'))
            f.truncate(0)

        clear_log_at = interaction.created_at.strftime('%Y-%m-%d-%H-%M-%S')

        file = discord.File(fp, filename=f'clear_by_{interaction.user.id}_at_{clear_log_at}.log')

        await interaction.followup.send("Log file cleared.\n`check backup file for old log data.`", file=file)

    @app_commands.command(name=_T('_load'), description=_T('Loads an extension.'))
    @app_commands.describe(extension=_T('extension name'))
    @app_commands.rename(extension=_T('extension'))
    @owner_only()
    async def load(self, interaction: Interaction, extension: initial_extensions) -> None:

        try:
            await self.bot.load_extension(f'{extension}')
            _log.info(f'Loading extension {extension}')
        except commands.ExtensionAlreadyLoaded:
            raise CommandError(f"The extension is already loaded.")
        except Exception as e:
            _log.error(e)
            raise CommandError('The extension load failed')
        else:
            embed = discord.Embed(description=f"Load : `{extension}`", color=0x8BE28B)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name=_T('_unload'), description=_T('Unload an extension'))
    @app_commands.describe(extension=_T('extension name'))
    @app_commands.rename(extension=_T('extension'))
    @owner_only()
    async def unload(self, interaction: Interaction, extension: initial_extensions) -> None:

        try:
            await self.bot.unload_extension(f'{extension}')
            _log.info(f'Unloading extension {extension}')
        except commands.ExtensionNotLoaded:
            raise CommandError(f'The extension was not loaded.')
        except Exception as e:
            _log.error(e)
            raise CommandError('The extension unload failed')
        else:
            embed = discord.Embed(description=f"Unload : `{extension}`", color=0x8BE28B)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name=_T('_reload'))
    @app_commands.describe(extension=_T('extension name'))
    @app_commands.rename(extension=_T('extension'))
    @owner_only()
    async def reload_(self, interaction: Interaction, extension: initial_extensions) -> None:
        """Reloads an extension."""

        try:
            await self.bot.reload_extension(f'{extension}')
            _log.info(f'Reloading extension {extension}')
        except commands.ExtensionNotLoaded:
            raise CommandError(f'The extension was not loaded.')
        except commands.ExtensionNotFound:
            raise CommandError(f'The Extension Not Found')
        except Exception as e:
            _log.error(e)
            raise CommandError('The extension reload failed')
        else:
            embed = discord.Embed(description=f"Reload : `{extension}`", color=0x8BE28B)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='_sync_tree')
    @app_commands.rename(guild_id=_T('guild_id'))
    @owner_only()
    async def sync_tree(self, interaction: Interaction, guild_id: int = None) -> None:

        await interaction.response.defer(ephemeral=True)

        if guild_id is not None:
            guild_object = discord.Object(id=guild_id)
            await self.bot.tree.sync(guild=guild_object)
            return
        await self.bot.tree.sync()

        embed = discord.Embed(description=f"Sync Tree", color=0x8BE28B)
        if guild_id is not None:
            embed.description = f"Sync Tree : `{guild_id}`"

        await self.bot.fetch_app_commands()

        await interaction.followup.send(embed=embed, ephemeral=True)

    # @load.autocomplete('extension')
    # @unload.autocomplete('extension')
    # @reload_.autocomplete('extension')
    # async def tags_autocomplete(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
    #     """Autocomplete for extension names."""
    #
    #     if interaction.user.id != self.bot.owner_id:
    #         return [
    #             app_commands.Choice(name='Only owner can use this command', value='Owner only can use this command')]
    #
    #     cogs = [extension.lower() for extension in self.bot._initial_extensions if extension.lower() != 'cogs.admin']
    #     return [app_commands.Choice(name=cog, value=cog) for cog in cogs]

    blacklist = app_commands.Group(
        name=_T('_blacklist'),
        description=_T('Blacklist commands'),
        default_permissions=discord.Permissions(
            administrator=True,
        ),
    )

    @blacklist.command(name='add', description=_T('Add user or guild to blacklist'))
    @app_commands.describe(object_id=_T('Object ID'))
    @owner_only()
    async def blacklist_add(self, interaction: Interaction, object_id: str) -> None:

        await interaction.response.defer(ephemeral=True)

        if object_id in self.bot.blacklist:
            raise CommandError(f'`{object_id}` is already in blacklist')

        await self.bot.add_to_blacklist(int(object_id))

        blacklist = (
            await self.bot.fetch_user(int(object_id))
            or self.bot.get_guild(int(object_id))
            or await self.bot.fetch_guild(int(object_id))
            or object_id
        )
        if isinstance(blacklist, (discord.User, discord.Guild)):
            blacklist = f"{blacklist} {inline(f'({blacklist.id})')}"

        embed = discord.Embed(description=f"{blacklist} are now blacklisted.", color=self.bot.theme.success)

        await interaction.followup.send(embed=embed)

    @blacklist.command(name=_T('remove'), description=_T('Remove a user or guild from the blacklist'))
    @app_commands.describe(object_id=_T('Object ID'))
    @owner_only()
    async def blacklist_remove(self, interaction: Interaction, object_id: str):

        await interaction.response.defer(ephemeral=True)

        if object_id not in self.bot.blacklist:
            raise CommandError(f'`{object_id}` is not in blacklist')

        await self.bot.remove_from_blacklist(int(object_id))

        blacklist = (
            await self.bot.fetch_user(int(object_id))
            or self.bot.get_guild(int(object_id))
            or await self.bot.fetch_guild(int(object_id))
            or object_id
        )

        if isinstance(blacklist, (discord.User, discord.Guild)):
            blacklist = f"{blacklist} {inline(f'({blacklist.id})')}"

        embed = discord.Embed(description=f"{blacklist} are now unblacklisted.", colour=self.bot.theme.success)

        await interaction.followup.send(embed=embed)

    @blacklist.command(name=_T('check'), description=_T('Check if a user or guild is blacklisted'))
    @app_commands.describe(object_id=_T('Object ID'))
    @owner_only()
    async def blacklist_check(self, interaction: Interaction, object_id: str):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(colour=self.bot.theme.error)

        if object_id in self.bot.blacklist:
            embed.description = f"{bold(object_id)} is blacklisted."
        else:
            embed.description = f"{bold(object_id)} is not blacklisted."
            embed.colour = self.bot.theme.success

        await interaction.followup.send(embed=embed)

    # @blacklist.command(name=_T('list'), description=_T('Lists all blacklisted users'))
    # @owner_only()
    # async def blacklist_list(self, interaction: Interaction):
    #
    #     await interaction.response.defer(ephemeral=True)
    #
    #     blacklist = self.bot.blacklist.all()

    # stat = app_commands.Group(
    #     name=_T('_stat'), description=_T('Stat commands'), default_permissions=discord.Permissions(administrator=True)
    # )
    #
    # @stat.command(name=_T('app_commands'))
    # @owner_only()
    # async def stat_app_commands(self, interaction: Interaction, guild_id: int = None):
    #     ...


async def setup(bot: LatteBot) -> None:
    if bot.support_guild_id is not None:
        await bot.add_cog(Developers(bot), guilds=[discord.Object(id=bot.support_guild_id)])
    else:
        _log.warning('Support guild id is not set. Developers cog will not be loaded.')
