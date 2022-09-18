from __future__ import annotations

import datetime
import json
import logging

import discord
from discord.ext import commands, tasks

from ._abc import MixinMeta
from ._client import RiotAuth
from ._sql_statements import RIOT_ACC_DELETE_BY_GUILD, RIOT_ACC_WITH_UPSERT

_log = logging.getLogger(__name__)


class Events(MixinMeta):
    @commands.Cog.listener()
    async def on_riot_re_authorized(self, riot_auth: RiotAuth, wait_for: bool) -> None:
        """Called when a user's riot account is updated"""

        print("on_riot_re_authorized")

        if wait_for:

            riot_acc_list = await self.get_riot_account(user_id=riot_auth.discord_id)
            for acc in riot_acc_list:
                if acc.puuid != riot_auth.puuid:
                    await acc.re_authorize(wait_for=False)

            # wait for re_authorize
            async with self.bot.pool.acquire() as conn:
                # Update the riot account in the database

                # single line
                old_data = self.users[riot_auth.discord_id]
                new_data = [riot_auth if auth_u.puuid == riot_auth.puuid else auth_u for auth_u in old_data]

                payload = [user_riot_auth.to_dict() for user_riot_auth in new_data]

                dumps_payload = json.dumps(payload)

                # encryption
                encrypt_payload = self.bot.encryption.encrypt(dumps_payload)

                await conn.execute(
                    RIOT_ACC_WITH_UPSERT,
                    riot_auth.discord_id,
                    riot_auth.guild_id,
                    encrypt_payload,
                    riot_auth.date_signed,
                    riot_auth.discord_id,
                )

            # invalidate cache
            self.get_riot_account.invalidate(self, user_id=riot_auth.discord_id)  # type: ignore

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when LatteBot leaves a guild"""

        # DELETE RETURNING
        async with self.bot.pool.acquire(timeout=180.0) as conn:
            records = await conn.fetch(RIOT_ACC_DELETE_BY_GUILD, guild.id)

            # remove for cache
            for record in records:
                user_id = record["user_id"]

                # invalidate cache
                self.get_riot_account.invalidate(self, user_id=user_id)  # type: ignore

    async def on_riot_account_error(self, user_id: int) -> None:
        """Called when a user's riot account is updated"""
        self.get_riot_account.invalidate(self, user_id=user_id)  # type: ignore

    # tasks

    # reset all cache every 7am UTC+7
    @tasks.loop(time=datetime.time(hour=0, minute=0, second=5))
    async def reset_cache(self) -> None:
        """Called every day at 7am UTC+7"""
        self.get_riot_account.cache_clear()  # type: ignore
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

    @tasks.loop(hours=1)
    async def client_version(self) -> None:
        print("client_version")
        # if self.valorant_client is None:
        #     return
        #
        # NEW_VERSION = await self.valorant_client._http._get_current_version()
        #
        # if NEW_VERSION != self.valorant_client.VERSION:
        #     await self.valorant_client.cache.fetch_all()

    # before loops tasks

    @auto_logout.before_loop
    @client_version.before_loop
    @featured_bundle_cache.before_loop
    @reset_cache.before_loop
    async def before_looping_task(self) -> None:
        await self.bot.wait_until_ready()
