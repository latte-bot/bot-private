from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING, Any, AnyStr, Callable, Dict, List, Optional, Union

import discord

from ._client import RiotAuth
from ._sql_statements import ACCOUNT_DELETE, ACCOUNT_DELETE_BY_GUILD, ACCOUNT_SELECT, ACCOUNT_SELECT_ALL, ACCOUNT_UPSERT

if TYPE_CHECKING:
    import asyncpg
    from typing_extensions import Self

    from bot import LatteBot


class ValorantUser:
    def __init__(self, record: Union[asyncpg.Record, Dict[str, Any]], bot: LatteBot) -> None:
        self._bot = bot
        self.user_id: int = record['user_id']
        self.guild_id: int = record['guild_id']
        self.locale: discord.Locale = (
            discord.enums.try_enum(discord.Locale, record['locale'])
            if not isinstance(record['locale'], discord.Locale)
            else record['locale']
        )
        self.date_signed: datetime.datetime = record['date_signed']
        self.extras: List[Dict[str, Any]] = (
            self.data_decrypted(record['extras'], to_dict=True)
            if not isinstance(record['extras'], list)
            else record['extras']
        )
        self._riot_accounts: List[RiotAuth] = [
            RiotAuth.from_db(
                self.user_id,
                self.guild_id,
                self.locale,
                bot,
                data,
            )
            for data in self.extras
        ]

    def encrypt(self, args: str) -> AnyStr:
        return self._bot.encryption.encrypt(args)

    def decrypt(self, token: AnyStr) -> str:
        return self._bot.encryption.decrypt(token)

    @property
    def id(self) -> int:
        return self.user_id

    def get_riot_accounts(self) -> List[RiotAuth]:
        return self._riot_accounts

    def get_1st(self) -> Optional[RiotAuth]:
        if len(self._riot_accounts) == 0:
            return None
        return self._riot_accounts[0]

    def remove_account(self, number: int) -> Optional[RiotAuth]:

        # data
        for acc in self.extras:
            if acc["acc_num"] == number:
                self.extras.remove(acc)

        for i, acc in enumerate(sorted(self.extras, key=lambda x: x["acc_num"])):
            acc["acc_num"] = i + 1

        # cache
        riot_auth = None
        for acc in self._riot_accounts:
            if acc.acc_num == number:
                self._riot_accounts.remove(acc)
                riot_auth = acc

        for i, acc in enumerate(sorted(self._riot_accounts, key=lambda x: x.acc_num)):
            acc.acc_num = i + 1

        return riot_auth

    def add_account(self, riot_auth: RiotAuth) -> None:
        self.extras.append(riot_auth.to_dict())
        self._riot_accounts.append(riot_auth)

        # sort by acc_num
        for index, acc in enumerate(sorted(self.extras, key=lambda x: x["acc_num"])):
            acc["acc_num"] = index + 1

        for index, acc in enumerate(sorted(self._riot_accounts, key=lambda x: x.acc_num)):
            acc.acc_num = index + 1

    def data_encrypted(self) -> AnyStr:
        return self.encrypt(json.dumps(self.extras))

    def data_decrypted(self, data: AnyStr, *, to_dict: bool = False) -> str:
        if not to_dict:
            return self.decrypt(data)
        return json.loads(self.decrypt(data))

    @classmethod
    def from_login(
        cls, riot_auth: RiotAuth, user_id: int, guild_id: int, locale: discord.Locale, bot: LatteBot
    ) -> Self:
        valorant_user = cls(
            record={
                'user_id': user_id,
                'guild_id': guild_id,
                'locale': locale,
                'date_signed': datetime.datetime.utcnow(),
                'extras': [riot_auth.to_dict()],
            },
            bot=bot,
        )
        return valorant_user


class Database:
    def __init__(self, bot: LatteBot) -> None:
        self.bot = bot
        self.pool = bot.pool

    async def select_users(self, *, conn: Optional[asyncpg.Pool] = None) -> List[ValorantUser]:
        conn = conn or self.pool
        data = await conn.fetch(ACCOUNT_SELECT_ALL)
        return [ValorantUser(d, self.bot) for d in data]

    async def select_user(self, user_id: int, *, conn: Optional[asyncpg.Pool] = None) -> Optional[ValorantUser]:
        conn = conn or self.pool
        row = await conn.fetchrow(ACCOUNT_SELECT, user_id)
        if row is None:
            return None
        return ValorantUser(row, self.bot)

    async def delete_user(self, user_id: int, *, conn: Optional[asyncpg.Pool] = None) -> str:
        conn = conn or self.pool
        return await conn.execute(ACCOUNT_DELETE, user_id)

    async def upsert_user(
        self,
        data: str,
        user_id: int,
        guild_id: int,
        locale: discord.Locale,
        date_signed: Optional[datetime.datetime] = datetime.datetime.now(),
        *,
        conn: Optional[asyncpg.Pool] = None,
    ) -> str:
        conn = conn or self.pool
        return await conn.execute(
            ACCOUNT_UPSERT,
            user_id,
            guild_id,
            data,
            date_signed,
            str(locale),
            user_id,
        )

    async def delete_by_guild(self, guild_id: int, *, conn: Optional[asyncpg.Pool] = None) -> List[asyncpg.Record]:
        conn = conn or self.pool
        return await conn.fetch(ACCOUNT_DELETE_BY_GUILD, guild_id)
