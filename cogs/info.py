from __future__ import annotations

import datetime
import itertools
import platform
from functools import cache
from typing import TYPE_CHECKING

import discord
import psutil
import pygit2

# import pkg_resources
from discord import Interaction, app_commands, ui

# i18n
from discord.app_commands import locale_str as _T
from discord.app_commands.checks import dynamic_cooldown
from discord.ext import commands
from discord.utils import format_dt

from utils.checks import cooldown_5s
from utils.emojis import LatteEmoji as Emoji
from utils.formats import count_python
from utils.useful import LatteCDN

if TYPE_CHECKING:
    from bot import LatteBot


class About(commands.Cog):
    """Latte's About command"""

    def __init__(self, bot: LatteBot) -> None:
        self.bot: LatteBot = bot
        self.process = psutil.Process()

    @property
    def display_emoji(self) -> discord.Emoji:
        return self.bot.get_emoji(998453861511610398)

    @staticmethod
    def format_commit(commit: pygit2.Commit) -> str:
        """format a commit"""
        short, _, _ = commit.message.partition('\n')
        short = short[0:40] + '...' if len(short) > 40 else short
        short_sha2 = commit.hex[0:6]
        commit_tz = datetime.timezone(datetime.timedelta(minutes=commit.commit_time_offset))
        commit_time = datetime.datetime.fromtimestamp(commit.commit_time).astimezone(commit_tz)
        offset = format_dt(commit_time, style='R')
        return f'[`{short_sha2}`](https://github.com/latte-bot/latte-bot/commit/{commit.hex}) {short} ({offset})'

    @property
    def get_last_parent(self) -> str:
        """Get the last parent of the repo"""
        repo = pygit2.Repository('./.git')
        parent = repo.head.target.hex
        return parent[0:6]

    @cache
    def get_latest_commits(self, limit: int = 3) -> str:
        """Get the latest commits from the repo"""
        repo = pygit2.Repository('./.git')
        commits = list(itertools.islice(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL), limit))
        return '\n'.join(self.format_commit(c) for c in commits)

    @app_commands.command(name=_T('invite'))
    @dynamic_cooldown(cooldown_5s)
    async def invite(self, interaction: Interaction) -> None:
        """Invite bot"""

        embed = discord.Embed(color=self.bot.theme.secondary)
        embed.set_author(
            name='{bot} ɪɴᴠɪᴛᴇ'.format(bot=self.bot.user.name),
            url=self.bot.invite_url,
            icon_url=self.bot.user.avatar,
        )
        embed.set_footer(text=f'{self.bot.user.name} | v{self.bot.version}')
        embed.set_image(url=str(LatteCDN.invite_banner))

        view = ui.View()
        view.add_item(ui.Button(label='ɪɴᴠɪᴛᴇ ᴍᴇ', url=self.bot.invite_url, emoji=str(Emoji.latte_icon)))

        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name=_T('about'))
    @dynamic_cooldown(cooldown_5s)
    async def about(self, interaction: Interaction) -> None:
        """Shows basic information"""

        core_dev = await self.bot.dev
        bot_version = self.bot.version
        server_count = len(self.bot.guilds)
        channel_count = len(list(self.bot.get_all_channels()))
        member_count = sum(guild.member_count for guild in self.bot.guilds)
        total_commands = len(self.bot.tree.get_commands())
        # dpy_version = pkg_resources.get_distribution("discord.py").version
        memory_usage = self.process.memory_full_info().uss / 1024 / 1024
        cpu_usage = self.process.cpu_percent()
        emoji = Emoji

        embed = discord.Embed(color=self.bot.theme.primacy, timestamp=interaction.created_at)
        embed.set_author(name='About Me', icon_url=self.bot.user.avatar)
        embed.add_field(name='ʟᴀᴛᴇꜱᴛ ᴜᴘᴅᴀᴛᴇꜱ:', value=self.get_latest_commits(), inline=False)
        embed.add_field(
            name='ꜱᴛᴀᴛꜱ:',
            value=f'{emoji.latte_icon} ꜱᴇʀᴠᴇʀꜱ: `{server_count}`\n'
            f'{emoji.member_icon} ᴜꜱᴇʀꜱ: `{member_count}`\n'
            f'{emoji.slash_command} ᴄᴏᴍᴍᴀɴᴅꜱ: `{total_commands}`\n'
            f'{emoji.channel_icon} ᴄʜᴀɴɴᴇʟ: `{channel_count}`',
            inline=True,
        )
        embed.add_field(
            name='ʙᴏᴛ ɪɴꜰᴏ:',
            value=f'{emoji.cursor} ʟɪɴᴇ ᴄᴏᴜɴᴛ: `{count_python(".")}`\n'
            f'{emoji.latte_icon} ʟᴀᴛᴛᴇ_ʙᴏᴛ: `{bot_version}`\n'
            f'{emoji.python} ᴘʏᴛʜᴏɴ: `{platform.python_version()}`\n'
            f'{emoji.discord_py} ᴅɪꜱᴄᴏʀᴅ.ᴘʏ: `{discord.__version__}`',
            inline=True,
        )
        embed.add_field(name='\u200b', value='\u200b', inline=True)
        embed.add_field(
            name='ᴘʀᴏᴄᴇꜱꜱ:',
            value=f'ᴏꜱ: `{platform.system()}`\n'
            f'ᴄᴘᴜ ᴜꜱᴀɢᴇ: `{cpu_usage}%`\n'
            f'ᴍᴇᴍᴏʀʏ ᴜꜱᴀɢᴇ: `{memory_usage:.2f} MB`',
            inline=True,
        )
        embed.add_field(
            name='ᴜᴘᴛɪᴍᴇ:',
            value=f'ʙᴏᴛ: {self.bot.launch_time}\n' f'ꜱʏꜱᴛᴇᴍ: <t:{round(psutil.boot_time())}:R>',
            inline=True,
        )
        embed.add_field(name='\u200b', value='\u200b', inline=True)
        embed.set_footer(text='ᴍᴀᴅᴇ ʙʏ {dev}'.format(dev=core_dev), icon_url=core_dev.avatar)

        view = ui.View()
        view.add_item(ui.Button(label='ꜱᴜᴘᴘᴏʀᴛ ꜱᴇʀᴠᴇʀ', url=self.bot.support_invite_url, emoji=str(emoji.latte_icon)))
        view.add_item(
            ui.Button(label='ᴅᴇᴠᴇʟᴏᴘᴇʀ', url=f'https://discord.com/users/{core_dev.id}', emoji=str(emoji.stacia_dev))
        )

        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name=_T('support'))
    @dynamic_cooldown(cooldown_5s)
    async def support(self, interaction: Interaction) -> None:
        """Sends the support server of the bot."""

        embed = discord.Embed(color=self.bot.theme.primacy)
        embed.set_author(name='ꜱᴜᴘᴘᴏʀᴛ:', icon_url=self.bot.user.avatar, url=self.bot.support_invite_url)
        embed.set_thumbnail(url=self.bot.user.avatar)

        view = ui.View()
        view.add_item(ui.Button(label='ꜱᴜᴘᴘᴏʀᴛ ꜱᴇʀᴠᴇʀ', url=self.bot.support_invite_url, emoji=str(Emoji.latte_icon)))
        view.add_item(
            ui.Button(
                label='ᴅᴇᴠᴇʟᴏᴘᴇʀ', url=f'https://discord.com/users/{self.bot.owner_id}', emoji=str(Emoji.stacia_dev)
            )
        )

        await interaction.response.send_message(embed=embed, view=view)

    # @app_commands.command(name=_("i18n"))
    # @dynamic_cooldown(cooldown_5s)
    # async def i18n(self, interaction: Interaction) -> None:
    #     """Shows the current language of the bot."""
    #
    #     repository = self.bot.i18n_repository
    #
    #     view = ui.View()

    # @app_commands.command(name=_('donate'))
    # @dynamic_cooldown(cooldown_5s)
    # async def donate(self, interaction: Interaction) -> None:
    #     """ บริจาค | Donate to the bot."""
    #     ...


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(About(bot))
