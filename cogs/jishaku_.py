from __future__ import annotations

import inspect
import io
import os
import pathlib
import sys
from typing import TYPE_CHECKING, Awaitable

import discord
import psutil
from discord import app_commands

# i18n
from discord.app_commands import locale_str as _T
from discord.ext import commands
from jishaku.codeblocks import Codeblock, codeblock_converter
from jishaku.cog import OPTIONAL_FEATURES, STANDARD_FEATURES
from jishaku.features.baseclass import Feature
from jishaku.features.root_command import natural_size
from jishaku.modules import ExtensionConverter, package_version
from jishaku.paginators import PaginatorInterface, WrappedPaginator, use_file_check

from utils.checks import owner_only
from utils.errors import CommandError

if TYPE_CHECKING:
    from bot import LatteBot

SUPPORT_GUILD_ID = int(os.getenv('SUPPORT_GUILD_ID'))
SUPPORT_GUILD = discord.Object(id=SUPPORT_GUILD_ID)


class Jishaku(*OPTIONAL_FEATURES, *STANDARD_FEATURES):

    if TYPE_CHECKING:
        bot: LatteBot

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.msg_jsk_py = app_commands.ContextMenu(
            name=_T('Python'), callback=self.message_jishaku_python, guild_ids=[self.bot.support_guild_id]
        )
        self.bot.tree.add_command(self.msg_jsk_py)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.msg_jsk_py.name, type=self.msg_jsk_py.type)
        await super().cog_unload()

    @Feature.Command(name="jishaku", aliases=["jsk"], invoke_without_command=True, ignore_extra=False)
    async def jsk(self, ctx: commands.Context) -> None:
        """
        The Jishaku debug and diagnostic commands.

        This command on its own gives a status brief.
        All other functionality is within its subcommands.
        """

        summary = [
            f"Jishaku v{package_version('jishaku')}, discord.py `{package_version('discord.py')}`, "
            f"`Python {sys.version}` on `{sys.platform}`".replace("\n", ""),
            f"Module was loaded <t:{self.load_time.timestamp():.0f}:R>, "
            f"cog was loaded <t:{self.start_time.timestamp():.0f}:R>.",
            "",
        ]

        try:
            proc = psutil.Process()

            with proc.oneshot():
                try:
                    mem = proc.memory_full_info()
                    summary.append(
                        f"Using {natural_size(mem.rss)} physical memory and "
                        f"{natural_size(mem.vms)} virtual memory, "
                        f"{natural_size(mem.uss)} of which unique to this process."
                    )
                except psutil.AccessDenied:
                    pass

                try:
                    name = proc.name()
                    pid = proc.pid
                    thread_count = proc.num_threads()

                    summary.append(f"Running on PID {pid} (`{name}`) with {thread_count} thread(s).")
                except psutil.AccessDenied:
                    pass

                summary.append("")  # blank line

        except psutil.AccessDenied:
            summary.append(
                "psutil is installed, but this process does not have high enough access rights "
                "to query process information."
            )
            summary.append("")  # blank line

        cache_summary = f"{len(self.bot.guilds)} guild(s) and {len(self.bot.users)} user(s)"

        # Show shard settings to summary
        if isinstance(self.bot, discord.AutoShardedClient):
            if len(self.bot.shards) > 20:
                summary.append(
                    f"This bot is automatically sharded ({len(self.bot.shards)} shards of {self.bot.shard_count})"
                    f" and can see {cache_summary}."
                )
            else:
                shard_ids = ', '.join(str(i) for i in self.bot.shards.keys())
                summary.append(
                    f"This bot is automatically sharded (Shards {shard_ids} of {self.bot.shard_count})"
                    f" and can see {cache_summary}."
                )
        elif self.bot.shard_count:
            summary.append(
                f"This bot is manually sharded (Shard {self.bot.shard_id} of {self.bot.shard_count})"
                f" and can see {cache_summary}."
            )
        else:
            summary.append(f"This bot is not sharded and can see {cache_summary}.")

        # pylint: disable=protected-access
        if self.bot._connection.max_messages:  # type: ignore
            message_cache = f"Message cache capped at {self.bot._connection.max_messages}"  # type: ignore
        else:
            message_cache = "Message cache is disabled"

        if discord.version_info >= (1, 5, 0):
            remarks = {True: 'enabled', False: 'disabled', None: 'unknown'}

            *group, last = (
                f"{intent.replace('_', ' ')} intent is {remarks.get(getattr(self.bot.intents, intent, None))}"
                for intent in ('presences', 'members', 'message_content')
            )

            summary.append(f"{message_cache}, {', '.join(group)}, and {last}.")
        else:
            guild_subscriptions = (
                f"guild subscriptions are " f"{'enabled' if self.bot._connection.guild_subscriptions else 'disabled'}"  # type: ignore  # noqa: E501
            )

            summary.append(f"{message_cache} and {guild_subscriptions}.")

        # pylint: enable=protected-access

        # Show websocket latency in milliseconds
        summary.append(f"Average websocket latency: {round(self.bot.latency * 1000, 2)}ms")

        embed = discord.Embed(color=self.bot.theme.primacy)
        embed.description = "\n".join(summary)

        await ctx.send(embed=embed)

    @Feature.Command(parent="jsk", name="source", aliases=["src"])
    async def jsk_source(self, ctx: commands.Context, *, command_name: str) -> None:
        """
        Displays the source code for an app command.
        """

        command = self.bot.get_command(command_name) or self.bot.tree.get_command(command_name)  # support app commands
        if not command:
            await ctx.send(f"Couldn't find command `{command_name}`.")
            return

        try:
            source_lines, _ = inspect.getsourcelines(command.callback)  # type: ignore
        except (TypeError, OSError):
            await ctx.send(f"Was unable to retrieve the source for `{command}` for some reason.")
            return

        filename = "source.py"

        try:
            filename = pathlib.Path(inspect.getfile(command.callback)).name  # type: ignore
        except (TypeError, OSError):
            pass

        # getsourcelines for some reason returns WITH line endings
        source_text = ''.join(source_lines)

        if use_file_check(ctx, len(source_text)):  # File "full content" preview limit
            await ctx.send(file=discord.File(filename=filename, fp=io.BytesIO(source_text.encode('utf-8'))))
        else:
            paginator = WrappedPaginator(prefix='```py', suffix='```', max_size=1980)

            paginator.add_line(source_text.replace('```', '``\N{zero width space}`'))

            interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
            await interface.send_to(ctx)

    @app_commands.command(name=_T('_jsk'))
    @app_commands.describe(sub=_T('Sub command of jsk'), args=_T('Arguments of jsk'))
    @app_commands.rename(sub=_T('sub'), args=_T('args'))
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def jishaku_app(
        self, interaction: discord.Interaction, sub: app_commands.Range[str, 1, 20] = None, args: str = None
    ) -> None:
        """Jishaku

        Attributes:
            sub (str): The subcommand to use.
            args (str): The arguments to pass to the subcommand.
        """

        async def jsk_codeblock(jishaku, context: commands.Context, codeblock: Codeblock) -> Awaitable[None]:
            try:
                return await jishaku(context, argument=codeblock)
            except Exception as e:
                raise CommandError('An error occurred while executing the codeblock.', e)

        await interaction.response.defer(ephemeral=True)

        ctx = await commands.Context.from_interaction(interaction)

        jishaku_command = 'jishaku' if sub is None else f'jishaku {sub}'

        jsk = self.bot.get_command(jishaku_command)

        if sub is None:
            return await jsk(ctx)

        if sub.isdigit():
            message_id = int(sub)
            message = await interaction.channel.fetch_message(message_id)
            if not message:
                raise CommandError(f"Couldn't find message with ID {message_id}.")
            await jsk_codeblock(jsk, ctx, codeblock_converter(message.content))
            return

        # root
        if sub in ['show', 'hide', 'tasks']:
            await jsk(ctx)
        elif sub in ['cancel']:
            await jsk(ctx, index=args)

        # invocation
        elif sub in ['override', 'execute', 'exec', 'override!', 'execute!', 'exec!']:
            await jsk(ctx, overrides=..., command_string=args)
        elif sub in ['repeat']:
            times = args.split(' ')
            await jsk(ctx, times=times[0], command_string=args.strip(times[0]))
        elif sub in ['debug', 'dbg']:
            await jsk(ctx, command_string=args)
        elif sub in ['source', 'src']:
            await jsk(ctx, command_name=args)

        # guild
        elif sub in ['permtrace']:
            try:
                args_0 = args.split(' ')[0]
                args_1 = args.split(' ')[1]
                channel = self.bot.get_channel(int(args_0))
                member = interaction.guild.get_member(int(args_1)) or await interaction.guild.fetch_member(int(args_1))
                role = interaction.guild.get_role(int(args_1))
            except (IndexError, ValueError):
                raise CommandError('Invalid arguments.')
            else:
                target = member if member else role
                await jsk(ctx, channel=channel, targets=target)

        # file system
        elif sub in ['curl', 'cat']:
            await jsk(ctx, args)

        # management
        elif sub in ['rtt', 'ping', 'shutdown', 'logout']:
            await jsk(ctx)
        elif sub in ['load', 'unload', 'reload']:
            cog = await ExtensionConverter().convert(ctx=ctx, argument=args)
            await jsk(ctx, cog)
        elif sub in ['sync']:
            await jsk(ctx, targets=args)
        elif sub in ['invite']:
            params = [args]
            await jsk(ctx, *params)

        # python
        elif sub in ['retain']:
            await jsk(ctx, toggle=args)
        elif sub in [
            'py',
            'python',
            'py_inspect',
            'pyi',
            'python_inspect',
            'pythoninspect',
            'dis',
            'disassemble',
            'ast',
            'timeit',
        ]:
            await jsk_codeblock(jsk, ctx, codeblock_converter(args))

        # shell
        if sub in [
            'shell',
            'bash',
            'sh',
            'powershell',
            'ps1',
            'ps',
            'cmd',
            'terminal',
            'git',
            'pip',
            'node',
            'pyright',
            'rustc',
        ]:
            await jsk_codeblock(jsk, ctx, codeblock_converter(args))

        # voice
        elif sub in ['join', 'connect']:
            destination = self.bot.get_channel(int(args)) or interaction.user
            await jsk(ctx, destination=destination)
        elif sub in ['play', 'play_local']:
            await jsk(ctx, uri=args)
        elif sub in ['voice', 'vc', 'stop', 'pause', 'resume', 'disconnect', 'dc']:
            await jsk(ctx)
        elif sub in ['volume']:
            await jsk(ctx, percentage=float(args))

        # youtube
        elif sub in ['youtube_dl', 'youtubedl', 'ytdl', 'yt']:
            await jsk(ctx, url=args)

    @owner_only()
    @app_commands.default_permissions(administrator=True)
    async def message_jishaku_python(self, interaction: discord.Interaction, message: discord.Message) -> None:
        """Jishaku Python"""

        if not message.content:
            raise CommandError('No code provided.')

        await interaction.response.defer(ephemeral=message.content.startswith('private'))

        content = message.content.removeprefix('private').strip()

        jsk = self.bot.get_command(f'jishaku py')
        ctx = await commands.Context.from_interaction(interaction)
        codeblock = codeblock_converter(content)

        try:
            await jsk(ctx, argument=codeblock)
        except Exception as e:
            print(e)
            raise CommandError('Invalid Python code.') from e


async def setup(bot: LatteBot) -> None:
    await bot.add_cog(Jishaku(bot=bot), guilds=[SUPPORT_GUILD])
