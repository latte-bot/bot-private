import asyncio
import contextlib
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import asyncpg

from bot import LatteBot

try:
    import uvloop  # type: ignore
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class RemoveNoise(logging.Filter):
    def __init__(self):
        super().__init__(name='discord.state')

    def filter(self, record):
        if record.levelname == 'WARNING' and 'referencing an unknown' in record.msg:
            return False
        return True


@contextlib.contextmanager
def setup_logging():

    log = logging.getLogger()

    try:
        # __enter__
        max_bytes = 32 * 1024 * 1024  # 32 MiB
        logging.getLogger('discord').setLevel(logging.INFO)
        logging.getLogger('discord.http').setLevel(logging.WARNING)
        logging.getLogger('discord.state').addFilter(RemoveNoise())

        log.setLevel(logging.INFO)
        handler = RotatingFileHandler(
            filename='_lattebot.log', encoding='utf-8', mode='w', maxBytes=max_bytes, backupCount=5
        )
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        fmt = logging.Formatter('[{asctime}] [{levelname:<7}] {name}: {message}', dt_fmt, style='{')
        handler.setFormatter(fmt)
        log.addHandler(handler)

        yield
    finally:
        # __exit__
        handlers = log.handlers[:]
        for handler in handlers:
            handler.close()
            log.removeHandler(handler)


def main():
    with setup_logging():
        asyncio.run(run_bot())


async def create_pool() -> asyncpg.Pool:
    def _encode_jsonb(value):
        return json.dumps(value)

    def _decode_jsonb(value):
        return json.loads(value)

    async def init(con):
        await con.set_type_codec(
            'jsonb',
            schema='pg_catalog',
            encoder=_encode_jsonb,
            decoder=_decode_jsonb,
            format='text',
        )

    #uri = os.getenv('POSTGRESQL', None)
    uri = 'postgres://rcymyytv:2kF8qAwPs1JZJe1QooE9CRVS6V_KRkdq@john.db.elephantsql.com/rcymyytv'
    if uri is None:
        raise RuntimeError('POSTGRESQL environment variable is not set')
    return await asyncpg.create_pool(
        uri,
        init=init,
        command_timeout=60,
        max_size=1,  # 20
        min_size=1,  # 20
    )  # type: ignore


async def run_bot():
    log = logging.getLogger()
    try:
        pool = await create_pool()
    except Exception:  # noqa
        log.exception('Could not set up PostgreSQL. Exiting.')
        return

    async with LatteBot() as bot:
        bot.set_debug('--debug' in sys.argv)
        bot.pool = pool
        await bot.start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format=f'%(asctime)s:%(levelname)s:%(name)s: %(message)s')
    with contextlib.suppress(KeyboardInterrupt):
        main()
