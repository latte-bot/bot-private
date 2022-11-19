from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

from discord.utils import MISSING

if TYPE_CHECKING:
    import discord
    import valorantx

    from bot import LatteBot

    from ._client import Client, RiotAuth
    from ._database import Database, ValorantUser


class MixinMeta(ABC):
    """Metaclass for mixin classes."""

    if TYPE_CHECKING:
        valorant_users: Dict[int, ValorantUser] = {}
        db: Database
        bot: LatteBot

    def __init__(self, *_args):
        self.v_client: Client = MISSING

    @abstractmethod
    async def fetch_user(self, *, id: int) -> ValorantUser:
        raise NotImplementedError()

    @abstractmethod
    def cache_clear(self) -> Any:
        """Clears the cache for assets."""
        raise NotImplementedError()

    @abstractmethod
    def cache_invalidate(self, riot_auth: RiotAuth) -> Any:
        """Invalidates the cache for a user."""
        raise NotImplementedError()

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
    def v_locale(locale: discord.Locale) -> Any:
        raise NotImplementedError()

    @abstractmethod
    async def invite_by_display_name(self, party: valorantx.Party, display_name: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _get_user(self, _id: int) -> Optional[ValorantUser]:
        raise NotImplementedError()

    @abstractmethod
    def set_valorant_user(self, user_id: int, guild_id: int, locale: discord.Locale, riot_auth: RiotAuth):
        raise NotImplementedError()

    @abstractmethod
    def add_riot_auth(self, _id: int, value: RiotAuth) -> None:
        raise NotImplementedError()
