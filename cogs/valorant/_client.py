from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Coroutine, Dict, Optional, Union

import aiohttp
import discord
import valorantx
from valorantx.client import _authorize_required
from valorantx.http import HTTPClient

# ext valorant
from valorantx.scraper import PatchNoteScraper
from valorantx.utils import MISSING

from ._custom import Agent, CompetitiveTier, ContentTier, Currency, GameMode, MatchDetails

if TYPE_CHECKING:
    import datetime

    from typing_extensions import Self

    from bot import LatteBot

_log = logging.getLogger(__name__)


class RiotAuth(valorantx.RiotAuth):
    def __init__(
        self,
        discord_id: int,
        guild_id: int = 0,
        bot: LatteBot = MISSING,
        **kwargs,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.discord_id: int = discord_id
        self.guild_id: int = guild_id
        self.acc_num: int = 1
        self.date_signed: Optional[datetime.datetime] = None

        # config
        self.hide_display_name: bool = kwargs.get('hide_display_name', False)
        self.notify_mode: bool = kwargs.get('notify_mode', False)
        self.locale: discord.Locale = discord.Locale.american_english
        self.night_market_is_opened: bool = False

        # multi factor
        self.__waif_for_2fa = True

    def __repr__(self) -> str:
        attrs = [
            ('discord_id', self.discord_id),
            ('display_name', self.display_name),
            ('acc_num', self.acc_num),
        ]
        inner = ' '.join('%s=%r' % t for t in attrs)
        return f'<{self.__class__.__name__} {inner}>'

    def __hash__(self) -> int:
        return hash(self.puuid)

    async def authorize_multi_factor(self, code: str, remember: bool = False):

        headers = {
            "Accept-Encoding": "deflate, gzip, zstd",
            "user-agent": RiotAuth.RIOT_CLIENT_USER_AGENT % "rso-auth",
            "Cache-Control": "no-assets",
            "Accept": "application/json",
        }

        data = {"type": "multifactor", "code": code, "rememberDevice": remember}

        conn = aiohttp.TCPConnector(ssl=self._auth_ssl_ctx)
        async with aiohttp.ClientSession(
            connector=conn,
            raise_for_status=True,
            cookie_jar=self._cookie_jar,
        ) as session:
            async with session.put(
                'https://auth.riotgames.com/api/v1/authorization',
                json=data,
                ssl=self._auth_ssl_ctx,
                headers=headers,
            ) as resp:
                data = await resp.json()

            self._cookie_jar = session.cookie_jar
            self.__set_tokens_from_uri(data)

            # region Get new entitlements token
            headers["Authorization"] = f"{self.token_type} {self.access_token}"
            async with session.post(
                "https://entitlements.auth.riotgames.com/api/token/v1",
                headers=headers,
                json={},
                # json={"urn": "urn:entitlement:%"},
            ) as r:
                self.entitlements_token = (await r.json())["entitlements_token"]

            # Get user info

            async with session.post('https://auth.riotgames.com/userinfo', headers=headers) as r:
                data = await r.json()
                self.puuid = data['sub']
                self.name = data['acct']['game_name']
                self.tag = data['acct']['tag_line']

            # Get regions

            body = {"id_token": self.id_token}
            async with session.put(
                'https://riot-geo.pas.si.riotgames.com/pas/v1/product/valorant', headers=headers, json=body
            ) as r:
                data = await r.json()
                self.region = data['affinities']['live']

            # endregion

    async def reauthorize(self, wait_for: bool = True) -> None:
        try_authorize = await super().reauthorize()
        if self.bot is not MISSING:
            if try_authorize:
                self.bot.dispatch('re_authorized_completion', self, wait_for)
            else:
                self.bot.dispatch('re_authorized_failure', self)

    # alias
    def re_authorize(self, wait_for: bool = True) -> Coroutine[Any, Any, None]:
        return self.reauthorize(wait_for=wait_for)

    def clear_cookie(self) -> None:
        self._cookie_jar.clear()

    def to_dict(self) -> Dict[str, Any]:

        cookie_dict = {}
        for domain, cookies in self._cookie_jar._cookies.items():  # type: ignore
            for cookie in cookies.values():
                cookie_dict[cookie.key] = cookie.value

        return {
            'access_token': self.access_token,
            'id_token': self.id_token,
            'token_type': self.token_type,
            'expires_at': self.expires_at,
            'entitlements_token': self.entitlements_token,
            'puuid': self.puuid,
            'name': self.name,
            'tag': self.tag,
            'region': self.region,
            'cookie': cookie_dict,
            'acc_num': self.acc_num,
            'hide_display_name': self.hide_display_name,
            'notify_mode': self.notify_mode,
            'night_market_is_opened': self.night_market_is_opened,
        }

    def from_data(self, data: Dict[str, Any]) -> None:
        self.access_token = data['access_token']
        self.id_token = data['id_token']
        self.token_type = data['token_type']
        self.expires_at = data['expires_at']
        self.entitlements_token = data['entitlements_token']
        self.puuid = data['puuid']
        self.name = data['name']
        self.tag = data['tag']
        self.region = data['region']
        self.acc_num = data['acc_num']
        self.hide_display_name = data.get('hide_display_name', False)
        self.notify_mode = data.get('notify_mode', False)
        self.night_market_is_opened = data.get('night_market_is_opened', False)

        self._cookie_jar = aiohttp.CookieJar()  # abc set in async function
        for key, value in data['cookie'].items():
            self._cookie_jar.update_cookies({key: value})

    @classmethod
    def from_db(cls, user_id: int, guild_id: int, locale: discord.Locale, bot: LatteBot, data: Dict[str, Any]) -> Self:
        riot_auth = cls(user_id, guild_id, bot=bot)
        riot_auth.locale = locale
        riot_auth.from_data(data)
        return riot_auth


class Client(valorantx.Client):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(locale=valorantx.Locale.american_english, **kwargs)
        self._http = HTTPClientCustom(self, self.loop)
        self._is_authorized = True

    @property
    def http(self) -> HTTPClientCustom:
        return self._http

    async def set_authorize(self, riot_auth: RiotAuth) -> Client:

        # set riot auth
        self.http._riot_auth = riot_auth
        self.http._puuid = riot_auth.user_id
        self.user = riot_auth

        # build headers
        self.http.clear_headers()
        await self.http.build_headers()

        return self

    # valorantx-scraper

    async def scraper_patch_note(self, url: str) -> PatchNoteScraper:
        text = await self.http.text_from_url(url)
        return PatchNoteScraper(text)

    # custom

    def get_agent(self, *args: Any, **kwargs: Any) -> Optional[Agent]:
        data = self._assets.get_agent(*args, **kwargs)
        return Agent(client=self, data=data) if data else None

    def get_content_tier(self, *args: Any, **kwargs: Any) -> Optional[ContentTier]:
        """:class:`Optional[ContentTier]`: Gets a content tier from the assets."""
        data = self._assets.get_content_tier(*args, **kwargs)
        return ContentTier(client=self, data=data) if data else None

    def get_currency(self, *args: Any, **kwargs: Any) -> Optional[Currency]:
        """:class:`Optional[Currency]`: Gets a currency from the assets."""
        data = self._assets.get_currency(*args, **kwargs)
        return Currency(client=self, data=data) if data else None

    def get_competitive_tier(self, *args: Any, **kwargs: Any) -> Optional[CompetitiveTier]:
        """:class:`Optional[CompetitiveTier]`: Gets a competitive tier from the assets."""
        data = self._assets.get_competitive_tier(*args, **kwargs)
        return CompetitiveTier(client=self, data=data) if data else None

    def get_game_mode(self, *args: Any, **kwargs: Any) -> Optional[GameMode]:
        """:class:`Optional[GameMode]`: Gets a game mode from the assets."""
        data = self._assets.get_game_mode(*args, **kwargs)
        return GameMode(client=self, data=data, **kwargs) if data else None

    @_authorize_required
    async def fetch_match_details(self, match_id: str) -> Optional[MatchDetails]:
        """|coro|

        Fetches the match details for a given match.

        Parameters
        ----------
        match_id: :class:`str`
            The match ID to fetch the match details for.

        Returns
        -------
        Optional[:class:`MatchDetails`]
            The match details for a given match.
        """
        match_details = await self.http.fetch_match_details(match_id)
        return MatchDetails(client=self, data=match_details)


class HTTPClientCustom(HTTPClient):

    super_user_id: int

    def __init__(self, client: Union[valorantx.Client, Client], loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(loop)
        self._client = client
        self._riot_auth: RiotAuth = MISSING
        self._riot_client_version: str = ''
        self._is_update_riot_client_version: bool = False

    @property
    def riot_auth(self) -> RiotAuth:
        return self._riot_auth

    def clear_headers(self) -> None:
        self._headers.clear()

    async def build_headers(self) -> None:
        await self.__build_headers()

    def to_update_riot_client_version(self) -> None:
        self._is_update_riot_client_version = True

    async def __build_headers(self) -> None:
        if self._riot_client_version == '' or self._is_update_riot_client_version:
            self._riot_client_version = await self._get_current_version()
            self._is_update_riot_client_version = False

        self._headers['Authorization'] = f"Bearer %s" % self._riot_auth.access_token
        self._headers['X-Riot-Entitlements-JWT'] = self._riot_auth.entitlements_token
        self._headers['X-Riot-ClientPlatform'] = self._client_platform
        self._headers['X-Riot-ClientVersion'] = self._riot_client_version
