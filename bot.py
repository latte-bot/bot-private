from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Type

import aiohttp
import asyncpg
import discord
from async_lru import alru_cache
from discord import app_commands, utils
from discord.ext import commands
from dotenv import load_dotenv

from utils.encryption import Encryption
from utils.enums import Theme
from utils.i18n import Translator

load_dotenv()

_log = logging.getLogger('latte_bot')

# jishaku
os.environ['JISHAKU_NO_UNDERSCORE'] = 'True'
os.environ['JISHAKU_HIDE'] = 'True'

initial_extensions = [
    'cogs.dev',
    'cogs.events',
    'cogs.errors',
    'cogs.help',
    'cogs.jishaku_',
    'cogs.info',
    'cogs.valorant',
]


class LatteBot(commands.AutoShardedBot):
    pool: asyncpg.Pool
    bot_app_info: discord.AppInfo

    def __init__(self) -> None:

        # intents
        intents = discord.Intents.default()
        intents.message_content = True

        # allowed_mentions
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)

        super().__init__(
            command_prefix=commands.when_mentioned,
            help_command=None,
            case_insensitive=True,
            allowed_mentions=allowed_mentions,
            intents=intents,
            # application_id=977433932146569216,
            application_id=989337541389987861,
        )

        # bot stuff
        self.launch_time = f'<t:{round(datetime.now().timestamp())}:R>'
        self.maintenance = False
        self.version = '2.0.0a'

        # bot theme
        self.theme: Type[Theme] = Theme

        # bot invite link
        self.invite_permission = 280576
        self.invite_url = discord.utils.oauth_url(
            self.application_id,
            permissions=discord.Permissions(self.invite_permission),
        )

        # extensions
        self._initial_extensions = initial_extensions

        # webhook
        self._webook_id = os.getenv('WEBHOOK_ID')
        self._webook_token = os.getenv('WEBHOOK_TOKEN')

        # activity
        self.bot_activity = 'LatteBot :)'

        # support guild stuff
        self.support_guild_id: int = int(os.getenv('SUPPORT_GUILD_ID'))

        self.support_invite_url = 'https://discord.gg/xeVJYRDY'

        # bot interaction checker
        self.tree.interaction_check = self.interaction_check
        self.maintenance_message = 'Bot is in maintenance mode.'  # TODO: localization support

        # encryption
        self.encryption = Encryption(os.getenv('CRYPTOGRAPHY'))

        # i18n stuff
        self.translator: Translator = utils.MISSING

        # http session stuff
        self.session: aiohttp.ClientSession = utils.MISSING

        # app commands stuff
        self._app_commands: Dict[str, app_commands.AppCommand] = {}

        # valorant
        self.riot_username: str = os.getenv('RIOT_USERNAME')
        self.riot_password: str = os.getenv('RIOT_PASSWORD')

    @property
    def owner(self) -> discord.User:
        """Returns the bot owner."""
        return self.bot_app_info.owner

    @property
    async def dev(self) -> Optional[discord.User]:
        """Returns discord.User of the owner"""
        return await self.fetch_user(self.owner_id)

    @property
    def support_guild(self) -> Optional[discord.Guild]:
        if self.support_guild_id is None:
            return None
        return self.get_guild(self.support_guild_id)

    @discord.utils.cached_property
    def webhook(self) -> discord.Webhook:
        wh_id, wh_token = int(self._webook_id), self._webook_token
        hook = discord.Webhook.partial(id=wh_id, token=wh_token, session=self.session)
        return hook

    @alru_cache(maxsize=1)
    async def fetch_app_commands(self) -> List[app_commands.AppCommand]:
        app_commands_list = await self.tree.fetch_commands()
        for app_cmd in app_commands_list:
            self._app_commands[app_cmd.name] = app_cmd
        return app_commands_list

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True
        # # self.locale = str(interaction.locale)
        #
        # if await self.is_owner(interaction.user):
        #     return True
        #
        # if not self.maintenance:  # if bot is in maintenance mode
        #     # todo maintenance message
        #     return True

    async def on_ready(self) -> None:

        await self.change_presence(
            # status=discord.Status.offline,  # dev mode = idle
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=self.bot_activity,
            ),
        )

        print(
            '\n\n'
            f'Logged in as: {self.user}\n'
            f'Activity: {self.bot_activity}\n'
            f'Servers: {len(self.guilds)}\n'
            f'Users: {sum(guild.member_count for guild in self.guilds)}'
            '\n\n'
        )

    async def load_cogs(self) -> None:
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception as e:
                print(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()

    async def setup_hook(self) -> None:

        # session
        if self.session is utils.MISSING:
            self.session = aiohttp.ClientSession()

        # i18n
        if self.translator is utils.MISSING:
            self.translator = Translator()
            await self.tree.set_translator(self.translator)

        # bot info
        self.bot_app_info = await self.application_info()
        self.owner_id = self.bot_app_info.owner.id

        # load cogs
        await self.load_cogs()

        # tree sync application commands
        await self.tree.sync()
        await self.tree.sync(guild=discord.Object(id=self.support_guild_id))
        # if 'cogs.admin' in self._initial_extensions and self.support_guild is not None:
        #     await self.tree.sync(guild=discord.Object(id=self.support_guild_id))

        # fetch app commands to cache
        await self.fetch_app_commands()

    async def close(self) -> None:
        await super().close()
        await self.pool.close()
        await self.session.close()

    async def start(self) -> None:
        await super().start(os.getenv('DISCORD_TOKEN'), reconnect=True)
