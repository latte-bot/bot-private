from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, List, Literal

from discord import Interaction, app_commands

# i18n
from discord.app_commands import locale_str as _T
from discord.app_commands.checks import dynamic_cooldown
from discord.ext import tasks

from utils.checks import cooldown_5s

from ._abc import MixinMeta

if TYPE_CHECKING:
    from ._abc import GetRiotAccount


class Notify(MixinMeta):  # noqa
    """Notify cog"""

    if TYPE_CHECKING:
        get_riot_account: GetRiotAccount

    async def send_notify(self):
        ...  # todo webhook send

    @tasks.loop(time=time(hour=0, minute=0, second=10))  # utc 00:00:15
    async def notify_alert(self) -> None:
        await self.send_notify()

    @notify_alert.before_loop
    async def before_daily_send(self) -> None:
        await self.bot.wait_until_ready()
        print('Checking new store skins for notifys...')

    notify = app_commands.Group(name=_T('notify'), description=_T('Notify commands'), guild_only=True)

    @notify.command(
        name=_T('add'), description=_T('Set a notification when a specific skin is available on your store')
    )
    @dynamic_cooldown(cooldown_5s)
    @app_commands.describe(skin=_T('The name of the skin you want to notify'))
    @app_commands.rename(skin=_T('skin'))
    async def notify_add(self, interaction: Interaction, skin: str) -> None:
        """Set a notification when a specific skin is available on your store"""
        ...

    @notify_add.autocomplete('skin')
    async def notify_add_autocomplete(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        ...

    @notify.command(name=_T('list'), description=_T('View skins you have set a for notification.'))
    @dynamic_cooldown(cooldown_5s)
    async def notify_list(self, interaction: Interaction) -> None:
        """View skins you have set a notification for"""
        ...

    @notify.command(name=_T('mode'), description=_T('Change notification mode'))
    @app_commands.describe(mode=_T('Choose notification'))
    @app_commands.choices(
        mode=[
            app_commands.Choice(name=_T('Specified Skin'), value=1),
            app_commands.Choice(name=_T('All Skin'), value=2),
            app_commands.Choice(name=_T('Off'), value=0),
        ]
    )
    @app_commands.rename(mode=_T('mode'))
    @dynamic_cooldown(cooldown_5s)
    async def notify_mode(self, interaction: Interaction, mode: app_commands.Choice[int]) -> None:
        """Set Skin Notifications mode"""
        ...

    @notify.command(name=_T('test'))
    @dynamic_cooldown(cooldown_5s)
    async def notify_test(self, interaction: Interaction) -> None:
        """Test Notifications"""
        ...
