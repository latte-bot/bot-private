import datetime
import io
import logging
import os
from typing import Dict, List, Optional, Type, Union

import aiohttp
import asyncpg
import discord
import valorantx
from colorthief import ColorThief
from discord import app_commands
from discord.ext import commands
from discord.utils import MISSING
from dotenv import load_dotenv

from utils.config import Config
from utils.emojis import LatteEmoji
from utils.encryption import Encryption
from utils.enums import Theme
from utils.i18n import Translator, _
from utils.useful import LatteCDN, Palette

load_dotenv()

_log = logging.getLogger('latte_bot')

# jishaku
os.environ['JISHAKU_NO_UNDERSCORE'] = 'True'
os.environ['JISHAKU_HIDE'] = 'True'

description = 'Hello, I am Latte, a bot made by @ꜱᴛᴀᴄɪᴀ.#7475 (240059262297047041)'

initial_extensions = (
    'cogs.test',
    'cogs.dev',
    'cogs.events',
    'cogs.fun',
    'cogs.errors',
    'cogs.help',
    'cogs.jishaku_',
    'cogs.info',
    'cogs.valorant',
)


class LatteBot(commands.AutoShardedBot):
    pool: asyncpg.Pool
    bot_app_info: discord.AppInfo

    def __init__(self) -> None:

        # intents
        intents = discord.Intents.default()

        # allowed_mentions
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)

        super().__init__(
            command_prefix=commands.when_mentioned,
            help_command=None,
            case_insensitive=True,
            allowed_mentions=allowed_mentions,
            intents=intents,
            description=description,
            # application_id=977433932146569216,
            application_id=989337541389987861,
            chunk_guilds_at_startup=False,
        )

        # bot stuff
        self.launch_time: str = f'<t:{round(datetime.datetime.now().timestamp())}:R>'
        self._maintenance: bool = False
        self._maintenance_time: Optional[datetime.datetime] = None
        self._debug: bool = False
        self._version: str = '2.0.0a'
        self._activity: str = 'nyanpasu ♡ ₊˚'
        self._initial_extensions = initial_extensions

        # assets
        self.theme: Type[Theme] = Theme
        self.l_emoji: Type[LatteEmoji] = LatteEmoji
        self.l_cdn: Type[LatteCDN] = LatteCDN

        # bot invite link
        self._permission_invite: int = 280576
        self.invite_url = discord.utils.oauth_url(
            self.application_id,
            permissions=discord.Permissions(self._permission_invite),
        )

        # webhook
        self._webhook_id: Optional[int] = os.getenv('WEBHOOK_ID')
        self._webhook_token: Optional[str] = os.getenv('WEBHOOK_TOKEN')

        # support guild
        self.support_guild_id: Optional[int] = int(os.getenv('SUPPORT_GUILD_ID'))
        self.support_invite_url: str = 'https://discord.gg/xeVJYRDY'

        # bot interaction checker
        self.tree.interaction_check = self.latte_check
        self.maintenance_message: str = _('Bot is in maintenance mode.')

        # encryption
        self.encryption: Encryption = Encryption(os.getenv('CRYPTOGRAPHY'))

        # i18n
        self.translator: Translator = MISSING

        # http session
        self.session: aiohttp.ClientSession = MISSING

        # app commands
        self._app_commands: Dict[str, Union[app_commands.AppCommand, app_commands.AppCommandGroup]] = {}

        # valorantx
        self.fake_user_id: int = 000000000000000000
        self.riot_username: str = os.getenv('RIOT_USERNAME')
        self.riot_password: str = os.getenv('RIOT_PASSWORD')

        # blacklisted users
        self.blacklist: Config[bool] = Config('blacklist.json')
        self.app_stats: Config[int] = Config('app_stats.json')

        # colour
        self.colors: Dict[str, List[Palette]] = {}

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
            raise ValueError('Support guild ID is not set.')
        return self.get_guild(self.support_guild_id)

    @discord.utils.cached_property
    def webhook(self) -> discord.Webhook:
        wh_id, wh_token = int(self._webhook_id), self._webhook_token
        if wh_id is None or wh_token is None:
            raise ValueError('Webhook ID or Token is not set.')
        hook = discord.Webhook.partial(id=wh_id, token=wh_token, session=self.session)
        return hook

    def is_maintenance(self) -> bool:
        return self._maintenance

    def is_debug(self) -> bool:
        return self._debug

    def set_debug(self, debug: bool) -> None:
        self._debug = debug

    @property
    def version(self) -> str:
        return self._version

    @version.setter
    def version(self, value: str) -> None:
        self._version = value

    @discord.utils.cached_property
    def traceback_log(self) -> discord.TextChannel:
        channel = self.get_channel(1002816710593749052)
        return channel

    async def on_message(self, message: discord.Message, /):
        if message.author == self.user:
            return
        await self.process_commands(message)

    async def add_to_blacklist(self, object_id: int):
        await self.blacklist.put(object_id, True)

    async def remove_from_blacklist(self, object_id: int):
        try:
            await self.blacklist.remove(object_id)
        except KeyError:
            pass

    async def get_or_fetch_member(self, guild: discord.Guild, member_id: int) -> Optional[discord.Member]:
        """Looks up a member in cache or fetches if not found.
        Parameters
        -----------
        guild: Guild
            The guild to look in.
        member_id: int
            The member ID to search for.
        Returns
        ---------
        Optional[Member]
            The member or None if not found.
        """

        member = guild.get_member(member_id)
        if member is not None:
            return member

        shard: discord.ShardInfo = self.get_shard(guild.shard_id)  # type: ignore  # will never be None
        if shard.is_ws_ratelimited():
            try:
                member = await guild.fetch_member(member_id)
            except discord.HTTPException:
                return None
            else:
                return member

        members = await guild.query_members(limit=1, user_ids=[member_id], cache=True)
        if not members:
            return None
        return members[0]

    async def fetch_app_commands(self) -> None:
        app_commands_list = await self.tree.fetch_commands()

        for fetch in app_commands_list:
            if fetch.type == discord.AppCommandType.chat_input:
                if len(fetch.options) > 0:
                    self._app_commands[fetch.name] = fetch
                    for option in fetch.options:
                        if isinstance(option, app_commands.AppCommandGroup):
                            self._app_commands[option.qualified_name] = option
                else:
                    self._app_commands[fetch.name] = fetch

    def get_app_command(self, name: str) -> Optional[app_commands.AppCommand]:
        return self._app_commands.get(name)

    def get_app_commands(self) -> List[app_commands.AppCommand]:
        return sorted(list(self._app_commands.values()), key=lambda c: c.name)

    async def latte_check(self, interaction: discord.Interaction) -> bool:

        if interaction.user.id in self.blacklist:
            await interaction.response.send_message(
                _('You are blacklisted from using this bot.'),
                ephemeral=True,
            )
            return False

        self.translator.set_locale(interaction.locale)

        if await self.is_owner(interaction.user):
            return True

        if not self.is_maintenance():
            return True

        return True

    def get_colors(self, id: str) -> List[Palette]:
        return self.colors.get(id)

    def set_colors(self, id: str, color: List[Palette]) -> None:
        self.colors[id] = color

    async def get_or_fetch_colors(
        self,
        id: str,
        image: Union[valorantx.Asset, discord.Asset, str],
        palette: int = 0,
    ) -> List[Palette]:
        color = self.get_colors(id)
        if color is None:

            if isinstance(image, valorantx.Asset):
                _file = await image.to_file(filename=id)
                to_bytes = _file.fp
            else:
                get_image = await self.session.get(image)
                to_bytes = io.BytesIO(await get_image.read())

            if palette > 0:
                get_color = ColorThief(to_bytes).get_palette(color_count=palette)
                color = [Palette(c) for c in get_color]
            else:
                color = [Palette(ColorThief(to_bytes).get_color())]

            self.set_colors(id, color)

        return color

    async def on_ready(self) -> None:

        _log.info(
            f'Logged in as: {self.user} '
            f'color: {self._activity} '
            f'Servers: {len(self.guilds)} '
            f'Users: {sum(guild.member_count for guild in self.guilds)}'
        )

        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name=self._activity),
            status=discord.Status.online if not self.is_maintenance() else discord.Status.idle,
        )

    async def load_cogs(self) -> None:
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception as e:
                _log.exception('Failed to load extension %s.', extension)

    async def setup_hook(self) -> None:

        # session
        if self.session is MISSING:
            self.session = aiohttp.ClientSession()

        # i18n
        if self.translator is MISSING:
            self.translator = Translator('./i18n')
            await self.tree.set_translator(self.translator)

        # bot info
        self.bot_app_info = await self.application_info()
        self.owner_id = self.bot_app_info.owner.id

        # localizations
        self.translator.load_string_localize()

        # load cogs
        await self.load_cogs()

        # tree translator app commands
        # tree_app_commands = self.tree.get_commands()
        # for command in tree_app_commands:
        #     await command.get_translated_payload(self.translator)

        # tree sync application commands
        # await self.tree.sync()
        sync_guilds = [
            # self.support_guild_id,
            # 1042503061454729289,  # EMOJI ABILITY 2
            # 1042502960921452734,  # EMOJI ABILITY 1
            # 1043965050630705182,  # EMOJI TIER
            # 1042501718958669965,  # EMOJI AGENT
            # 1042809126624964651,  # EMOJI MATCH
        ]
        for guild_id in sync_guilds:
            try:
                await self.tree.sync(guild=discord.Object(id=guild_id))
            except Exception as e:
                _log.exception(f'Failed to sync guild {guild_id}.')

        # await Translator.get_i18n(
        #     cogs=self.cogs,
        #     excludes=['developers', 'jishaku', 'testing'],  # exclude cogs
        #     only_public=True,  # exclude @app_commands.guilds()
        #     set_locale=[discord.Locale.american_english, discord.Locale.thai],  # locales to create
        # )

        await self.fetch_app_commands()

    async def close(self) -> None:
        await super().close()
        await self.pool.close()
        await self.session.close()

    async def start(self) -> None:
        await super().start(os.getenv('DISCORD_TOKEN'), reconnect=True)
