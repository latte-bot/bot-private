from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any, Coroutine, Dict, Union

import aiohttp
import valorant
from valorant.http import HTTPClient
from valorant.utils import MISSING

if TYPE_CHECKING:
    from bot import LatteBot

_log = logging.getLogger(__name__)


class RiotAuth(valorant.RiotAuth):
    def __init__(self, discord_id: int, bot: LatteBot = MISSING, **kwargs) -> None:
        super().__init__()
        self.bot = bot
        self.discord_id: int = discord_id
        self.guild_id: int = 0
        self.date_signed: Union[datetime.datetime, int] = 0
        self.acc_num: int = 1

        # config
        self.hide_display_name: bool = kwargs.get('hide_display_name', False)
        self.notify_mode: int = kwargs.get('notify_mode', 0)

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
            print(f"{self.token_type} {self.access_token}")
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
        }

    async def from_dict(self, data: Dict[str, Any]) -> None:
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
        self.notify_mode = data.get('notify_mode', 0)

        self._cookie_jar = aiohttp.CookieJar()  # abc set in async function
        for key, value in data['cookie'].items():
            self._cookie_jar.update_cookies({key: value})


class Client(valorant.Client):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(locale=valorant.Locale.american_english, **kwargs)
        self._http = HTTPClientCustom(self)
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


class HTTPClientCustom(HTTPClient):

    super_user_id: int

    def __init__(self, client: Union[valorant.Client, Client]) -> None:
        super().__init__()
        self._client = client
        self._riot_auth: RiotAuth = MISSING
        self._next_fetch_client_version: int = 0
        # self._puuid: Optional[str] = self._riot_auth.user_id if self._riot_auth is not MISSING else None

    @property
    def riot_auth(self) -> RiotAuth:
        return self._riot_auth

    def clear_headers(self) -> None:
        self._headers.clear()

    async def build_headers(self) -> None:
        await self.__build_headers()

    async def __build_headers(self) -> None:

        self._next_fetch_client_version += 1
        if self._riot_client_version == '' or self._next_fetch_client_version >= 30:
            self._riot_client_version = await self._get_current_version()
        self._headers['Authorization'] = f"Bearer %s" % self._riot_auth.access_token
        self._headers['X-Riot-Entitlements-JWT'] = self._riot_auth.entitlements_token
        self._headers['X-Riot-ClientPlatform'] = self._client_platform
        self._headers['X-Riot-ClientVersion'] = self._riot_client_version
