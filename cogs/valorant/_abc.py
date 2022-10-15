from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional, Protocol, TypeVar, runtime_checkable

from discord.utils import MISSING

if TYPE_CHECKING:
    import ssl

    import aiohttp
    import discord

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

    @abstractmethod
    def clear_cache_assets(self) -> Any:
        """Clears the cache for assets."""
        pass

    @abstractmethod
    def cache_get_invalidate(self, riot_auth: RiotAuth) -> Any:
        """Invalidates the cache for a user."""
        pass

    @abstractmethod
    def get_all_agents(self) -> Any:
        """Gets all agents."""
        raise NotImplementedError()

    @abstractmethod
    def get_all_bundles(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_buddies(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_buddy_levels(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_player_cards(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_player_titles(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_sprays(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_spray_levels(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_skins(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_skin_levels(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_skin_chromas(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def get_all_weapons(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    async def get_patch_notes(self, locale: discord.Locale) -> Any:
        raise NotImplementedError()

    @abstractmethod
    async def get_featured_bundle(self) -> Any:
        raise NotImplementedError()

    @staticmethod
    def locale_converter(locale: discord.Locale) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def invite_by_display_name(self, target_id: str, display_name: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def get_user(self, _id: int) -> Optional[List[RiotAuth]]:
        raise NotImplementedError()

    @abstractmethod
    def set_user(self, _id: int, value: List[RiotAuth]) -> None:
        raise NotImplementedError()

    @abstractmethod
    def add_user(self, _id: int, value: RiotAuth) -> None:
        raise NotImplementedError()
