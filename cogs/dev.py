from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING, Literal

import discord
from discord import Interaction, app_commands

# i18n
from discord.app_commands import locale_str as _T
from discord.ext import commands

from utils.checks import owner_only
from utils.errors import CommandError

if TYPE_CHECKING:
    from bot import LatteBot

SUPPORT_GUILD_ID = int(os.getenv('SUPPORT_GUILD_ID'))
SUPPORT_GUILD = discord.Object(id=SUPPORT_GUILD_ID)

initial_extensions = Literal['cogs.events', 'cogs.errors', 'cogs.help', 'cogs.jishaku', 'cogs.info', 'cogs.valorant']


class Developers(commands.Cog):
    """Developers commands"""

    def __init__(self, bot: LatteBot) -> None:
        self.bot: LatteBot = bot

    latte_log = app_commands.Group(
        name="_log",
        description="latte bot personal commands",
        default_permissions=discord.Permissions(
            administrator=True,
        ),
    )

    @latte_log.command(name=_T('read'))
    @app_commands.describe(to_file=_T('send the log file as a file'))
    @app_commands.rename(to_file=_T('to_file'))
    @owner_only()
    async def latte_log_read(self, interaction: discord.Interaction, to_file: bool = False) -> None:
        """Read the latte log"""

        await interaction.response.defer(ephemeral=True)
        if not to_file:
            ctx = await commands.Context.from_interaction(interaction)
            jsk = self.bot.get_command('jishaku cat')

            await jsk(ctx, '_lattebot.log')
        else:
            with open('_lattebot.log', 'r+', encoding="utf-8") as f:
                fp = io.BytesIO(f.read().encode('utf-8'))
                await interaction.followup.send(file=discord.File(fp, 'lattebot.log'))

    @latte_log.command(name=_T('clear'))
    @owner_only()
    async def latte_log_clear(self, interaction: discord.Interaction) -> None:
        """Clear the latte log"""

        await interaction.response.defer(ephemeral=True)

        with open('_lattebot.log', mode='r+', encoding='utf-8') as f:
            fp = io.BytesIO(f.read().encode('utf-8'))
            f.truncate(0)

        clear_log_at = interaction.created_at.strftime('%Y-%m-%d-%H-%M-%S')

        file = discord.File(fp, filename=f'clear_by_{interaction.user.id}_at_{clear_log_at}.log')

        await interaction.followup.send("Log file cleared.\n`check backup file for old log data.`", file=file)

    @app_commands.command(name=_T('_load'))
    @app_commands.describe(extension=_T('extension name'))
    @app_commands.rename(extension=_T('extension'))
    @owner_only()
    async def load(self, interaction: Interaction, extension: initial_extensions) -> None:
        """Loads an extension."""

        try:
            await self.bot.load_extension(f'{extension}')
        except commands.ExtensionAlreadyLoaded:
            raise CommandError(f"The extension is already loaded.")
        except Exception as e:
            print(e)
            raise CommandError('The extension load failed')
        else:
            embed = discord.Embed(description=f"Load : `{extension}`", color=0x8BE28B)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name=_T('_unload'))
    @app_commands.describe(extension=_T('extension name'))
    @app_commands.rename(extension=_T('extension'))
    @owner_only()
    async def unload(self, interaction: Interaction, extension: initial_extensions) -> None:
        """Unloads an extension."""

        try:
            await self.bot.unload_extension(f'{extension}')
        except commands.ExtensionNotLoaded:
            raise CommandError(f'The extension was not loaded.')
        except Exception as e:
            print(e)
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
            print(f"Reloading {extension}")
            await self.bot.reload_extension(f'{extension}')
        except commands.ExtensionNotLoaded:
            raise CommandError(f'The extension was not loaded.')
        except commands.ExtensionNotFound:
            raise CommandError(f'The Extension Not Found')
        except Exception as e:
            print(e)
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

        self.bot.fetch_app_commands.cache_clear()

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

    # TODO: blacklist command
    blacklist = app_commands.Group(
        name=_T('_blacklist'), description=_T('Blacklist commands'), guild_ids=[SUPPORT_GUILD_ID]
    )

    @blacklist.command(name='add')
    @app_commands.describe(snowflake_id=_T('Snowflake ID'), reason=_T('The reason for blacklisting the user'))
    @owner_only()
    async def blacklist_add(self, interaction: Interaction, snowflake_id: int, reason: str):
        """Blacklist a user or guild"""

        await interaction.response.defer(ephemeral=True)

        await self.bot.add_blacklist(snowflake_id, reason)
        embed = discord.Embed(description=f"**{snowflake_id}** are now blacklisted.")

        await interaction.followup.send(embed=embed)

    @blacklist.command(name=_T('remove'))
    @app_commands.describe(snowflake_id=_T('Snowflake ID'))
    @owner_only()
    async def blacklist_remove(self, interaction: Interaction, snowflake_id: int):
        """Remove a user or guild from the blacklist"""

        await interaction.response.defer(ephemeral=True)

        await self.bot.remove_blacklist(snowflake_id)
        embed = discord.Embed(description=f"**{snowflake_id}** are now removed from the blacklist.")

        await interaction.followup.send(embed=embed)

    @blacklist.command(name=_T('check'))
    @app_commands.describe(snowflake_id=_T('Snowflake ID'))
    @owner_only()
    async def blacklist_check(self, interaction: Interaction, snowflake_id: int):
        """Check if a user or guild is blacklisted"""
        await interaction.response.defer(ephemeral=True)

        if await self.bot.is_blacklisted(snowflake_id):
            embed = discord.Embed(description=f"**{snowflake_id}** is blacklisted.")
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(description=f"**{snowflake_id}** is not blacklisted.")

        await interaction.followup.send(embed=embed)

    @blacklist.command(name=_T('list'))
    @owner_only()
    async def blacklist_list(self, interaction: Interaction):
        """Lists all blacklisted users"""

        await interaction.response.defer(ephemeral=True)

        blacklist = await self.bot.get_blacklist()
        # todo paginate


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Developers(bot), guilds=[SUPPORT_GUILD])
