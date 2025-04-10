from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

import discord
from discord import Interaction, Member, User, app_commands
from discord.app_commands import locale_str as _T
from discord.app_commands.checks import dynamic_cooldown
from discord.ext import commands

from utils.checks import cooldown_5s

if TYPE_CHECKING:
    from bot import LatteBot


class Fun(commands.Cog):
    """Fun commands"""

    def __init__(self, bot: LatteBot) -> None:
        self.bot: LatteBot = bot

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='🥳')

    @app_commands.command(name=_T('latte_say'), description=_T('Message something you give latte to say'))
    @app_commands.describe(message=_T('Input message'), attachment=_T('The attachment to send'))
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def latte_say(self, interaction: Interaction, message: str, attachment: Optional[discord.Attachment] = None):

        files = []
        if attachment is not None:
            files.append(await attachment.to_file(spoiler=attachment.is_spoiler()))

        await interaction.response.send_message('\u200b', ephemeral=True)
        await interaction.channel.send(f'{message}', allowed_mentions=discord.AllowedMentions.none(), files=files)

    @app_commands.command(name=_T('saybot'), description=_T('Message something you give saybot to say'))
    @app_commands.describe(
        message=_T('Input message'),
        member=_T('The member to say something to saybot'),
        attachment=_T('The attachment to send'),
    )
    # @app_commands.default_permissions(manage_webhooks=True)
    @app_commands.checks.has_permissions(manage_webhooks=True)
    @app_commands.guild_only()
    @dynamic_cooldown(cooldown_5s)
    async def saybot(
        self,
        interaction: Interaction,
        message: str = '\u200b',
        attachment: Optional[discord.Attachment] = None,
        member: Optional[Union[Member, User]] = None,
    ):

        await interaction.response.defer(ephemeral=True)

        if len(await interaction.channel.webhooks()) >= 10:
            raise commands.BadArgument('Too many webhooks in this channel')

        member = member or interaction.user

        files = []
        if attachment is not None:
            files.append(await attachment.to_file(spoiler=attachment.is_spoiler()))

        webhook = await interaction.channel.create_webhook(name=member.display_name)
        # TODO: check type of channel thread or not

        await webhook.send(
            content=message,
            username=member.display_name,
            avatar_url=member.display_avatar,
            files=files,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await webhook.delete()
        await interaction.followup.send('\u200b')


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Fun(bot))
