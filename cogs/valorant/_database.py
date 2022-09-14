from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING, Optional

from utils import database as db

if TYPE_CHECKING:
    import asyncpg

    from bot import LatteBot


class RiotAccount(db.Table, table_name='riot_accounts'):
    user_id = db.Column(db.Integer(big=True), primary_key=True)
    extras = db.Column(db.String)
    date_signed = db.Column(db.Datetime)


class RiotAccountConfig:

    __slots__ = (
        'bot',
        'id',
        'guild_id',
        'puuid',
        'name',
        'tagline',
        'region',
        'ssid_token',
        'access_token',
        'id_token',
        'entitlements_token',
        'date_signed',
    )

    def __init__(self, *, user_id: int, bot: LatteBot, record: Optional[asyncpg.Record] = None):
        self.id: int = user_id
        self.bot: LatteBot = bot

        if record:

            # encryption
            decrypt_extras = self.bot.encryption.decrypt(record['extras'])
            extras = json.loads(decrypt_extras)

            # user data
            self.guild_id = record['guild_id']
            self.puuid = extras['puuid']
            self.name = extras['name']
            self.tagline = extras['tagline']
            self.region = extras['region']

            # cookies and tokens
            self.ssid_token: str = extras['ssid_token']
            self.access_token: str = extras['access_token']
            self.id_token: str = extras['id_token']
            self.entitlements_token: str = extras['entitlements_token']

            # date signed
            self.date_signed: datetime.datetime = record['date_signed']

            self.refresh_access_token()

    def refresh_access_token(self):
        if self.access_token_expired:
            redeem = Auth.redeem_cookies(self.ssid_token)
            if redeem.auth_type == AuthResponseType.response:
                self.ssid_token = redeem.ssid_token
                self.access_token = redeem.access_token
                self.id_token = redeem.id_token
                self.entitlements_token = redeem.entitlements_token

                payload = dict(
                    puuid=self.puuid,
                    name=self.name,
                    tagline=self.tagline,
                    region=self.region,
                    ssid_token=self.ssid_token,
                    access_token=self.access_token,
                    id_token=self.id_token,
                    entitlements_token=self.entitlements_token,
                )

                encrypt_payload = self.bot.encryption.encrypt(json.dumps(payload))

                # dispatch riot_account_updated event
                self.bot.dispatch('riot_account_updated', self.id, encrypt_payload)

    @property
    def display_name(self) -> str:
        return f'{self.name}#{self.tagline}'

    @property
    def access_token_expired(self) -> bool:
        jwt = self.bot.encryption.jwt_decode_without_verify(self.access_token)
        return jwt.get('exp') < int(datetime.datetime.now().timestamp())
