from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Union

import discord
from discord import Interaction
from discord.app_commands import Command, ContextMenu
from discord.ext import commands

if TYPE_CHECKING:
    from bot import LatteBot

_log = logging.getLogger(__name__)


class Event(commands.Cog):
    """Bot Events"""

    def __init__(self, bot: LatteBot) -> None:
        self.bot: LatteBot = bot

    @discord.utils.cached_property
    def webhook(self) -> discord.Webhook:
        wh_id, wh_token = self.bot._webhook_id, self.bot._webhook_token
        hook = discord.Webhook.partial(id=wh_id, token=wh_token, session=self.bot.session)
        return hook

    @commands.Cog.listener('on_app_command_completion')
    async def on_latte_command_completion(self, interaction: Interaction, command: Union[Command, ContextMenu]) -> None:
        """Called when a command is completed"""

        if interaction.user == self.bot.owner:
            return

        data = self.bot.app_stats.get(command.name)
        if data is not None:
            await self.bot.app_stats.put(command.name, data + 1)
        else:
            await self.bot.app_stats.put(command.name, 1)

    async def send_guild_stats(self, embed: discord.Embed, guild: discord.Guild):
        """Send guild stats to webhook"""

        member_count = guild.member_count or 1

        embed.description = (
            f'**ɴᴀᴍᴇ:** {discord.utils.escape_markdown(guild.name)} • `{guild.id}`\n' f'**ᴏᴡɴᴇʀ:** `{guild.owner_id}`'
        )
        embed.add_field(name='ᴍᴇᴍʙᴇʀ ᴄᴏᴜɴᴛ', value=f'{member_count}', inline=True)
        embed.set_thumbnail(url=guild.icon)
        embed.set_footer(text=f'ᴛᴏᴛᴀʟ ɢᴜɪʟᴅꜱ: {len(self.bot.guilds)}')

        if guild.me:
            embed.timestamp = guild.me.joined_at

        await self.webhook.send(embed=embed)

    @commands.Cog.listener('on_guild_join')
    async def on_latte_join(self, guild: discord.Guild) -> None:
        """Called when LatteBot joins a guild"""

        if guild.id in self.bot.blacklist:
            _log.info(f'Left guild {guild.id} because it is blacklisted')
            return await guild.leave()

        embed = discord.Embed(title='ᴊᴏɪɴᴇᴅ ꜱᴇʀᴠᴇʀ', colour=0x52D452)
        await self.send_guild_stats(embed, guild)

    @commands.Cog.listener('on_guild_remove')
    async def on_latte_leave(self, guild: discord.Guild) -> None:
        """Called when LatteBot leaves a guild"""
        embed = discord.Embed(title='ʟᴇꜰᴛ ꜱᴇʀᴠᴇʀ', colour=0xFF6961)
        await self.send_guild_stats(embed, guild)


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Event(bot))
