from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Awaitable, Callable, Dict, List, Optional, Protocol, TypeVar, runtime_checkable

from discord.utils import MISSING

if TYPE_CHECKING:
    import ssl

    import aiohttp

    from bot import LatteBot

    from ._client import Client, RiotAuth

C = TypeVar('C', bound=Callable)


@runtime_checkable
class GetRiotAccount(Protocol[C]):
    """Protocol for getting a user's Riot account."""

    _auth_ssl_ctx: ssl.SSLContext
    _cookie_jar: aiohttp.CookieJar
    access_token: Optional[str]
    scope: Optional[str]
    id_token: Optional[str]
    token_type: Optional[str]
    expires_at: int
    user_id: Optional[str]
    entitlements_token: Optional[str]
    name: Optional[str]
    tag: Optional[str]
    bot: LatteBot
    discord_id: int
    acc_num: int

    def __call__(self, *, user_id: int) -> Awaitable[List[RiotAuth]]:
        pass


class MixinMeta(ABC):
    """Metaclass for mixin classes."""

    if TYPE_CHECKING:
        get_riot_account: GetRiotAccount
        users: Dict[int, List[RiotAuth]] = {}

    def __init__(self, *_args):
        self.bot: LatteBot = MISSING
        self.v_client: Client = MISSING
