from __future__ import annotations

import datetime
import json
import logging

import discord
from discord.ext import commands, tasks

from ._abc import MixinMeta
from ._client import RiotAuth
from ._sql_statements import ACCOUNT_DELETE_BY_GUILD

_log = logging.getLogger(__name__)


class Events(MixinMeta):  # noqa
    @commands.Cog.listener()
    async def on_re_authorized_completion(self, riot_auth: RiotAuth, wait_for: bool) -> None:
        """Called when a user's riot account is updated"""

        if wait_for:

            v_user = await self.fetch_user(id=riot_auth.discord_id)
            for acc in v_user.get_riot_accounts():
                if acc.puuid != riot_auth.puuid:
                    await acc.re_authorize(wait_for=False)

            # wait for re_authorize
            async with self.bot.pool.acquire() as conn:
                # Update the riot account in the database

                old_data = self._get_user(riot_auth.discord_id)
                if old_data is not None:
                    new_data = [
                        riot_auth if auth_u.puuid == riot_auth.puuid else auth_u
                        for auth_u in old_data.get_riot_accounts()
                    ]

                    payload = [user_riot_auth.to_dict() for user_riot_auth in new_data]

                    dumps_payload = json.dumps(payload)

                    # encryption
                    encrypt_payload = self.bot.encryption.encrypt(dumps_payload)

                    await self.db.upsert_user(
                        encrypt_payload,
                        v_user.id,
                        v_user.guild_id,
                        v_user.locale,
                        v_user.date_signed,
                        conn=conn,
                    )

            # invalidate cache
            self.fetch_user.invalidate(self, id=riot_auth.discord_id)  # type: ignore

    @commands.Cog.listener()
    async def on_re_authorized_failure(self, riot_auth: RiotAuth) -> None:
        """Called when a user's riot account fails to update"""
        self.cache_invalidate(riot_auth)  # validate cache

    async def on_riot_account_error(self, user_id: int) -> None:
        """Called when a user's riot account is updated"""
        self.fetch_user.invalidate(self, id=user_id)  # type: ignore

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when LatteBot leaves a guild"""

        async with self.bot.pool.acquire(timeout=180.0) as conn:
            records = await self.db.delete_by_guild(guild.id, conn=conn)

            # remove for cache
            for record in records:
                user_id = record["user_id"]

                # invalidate cache
                self.fetch_user.invalidate(self, id=user_id)  # type: ignore

    # tasks

    # reset all cache every 7am UTC+7
    @tasks.loop(time=datetime.time(hour=0, minute=0, second=5))
    async def reset_cache(self) -> None:
        """Called every day at 7am UTC+7"""
        self.fetch_user.cache_clear()  # type: ignore
        self.store_func.cache_clear()  # type: ignore
        self.battlepass_func.cache_clear()  # type: ignore

    # @tasks.loop(time=time(hour=0))
    @tasks.loop(seconds=10)
    async def auto_logout(self):
        """Logout all users who have logged in for more than 30 days"""
        # delete_query = """DELETE FROM riot_accounts WHERE logout_at < $1"""
        # await self.bot.pool.execute(delete_query, datetime.now())

    @tasks.loop(hours=12)
    async def featured_bundle_cache(self) -> None:
        self.get_featured_bundle.cache_clear()  # type: ignore

    @tasks.loop(time=datetime.time(hour=17, minute=0, second=0))  # looping every 00:00:00 UTC+7
    async def client_version(self) -> None:

        version = await self.v_client.get_valorant_version()

        if version is None:
            return

        if version != self.v_client.version:
            self.v_client.version = version
            # login super user
            await self.v_client.fetch_assets(force=True, reload=True)
            self.v_client.http.to_update_riot_client_version()
            self.v_client.http.riot_auth.RIOT_CLIENT_USER_AGENT = version.riot_client_build
            self.cache_clear()

    # before loops tasks

    @auto_logout.before_loop
    @client_version.before_loop
    @featured_bundle_cache.before_loop
    @reset_cache.before_loop
    async def before_looping_task(self) -> None:
        await self.bot.wait_until_ready()
