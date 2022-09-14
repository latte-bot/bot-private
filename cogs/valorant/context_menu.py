from discord import Interaction, Member
from discord.app_commands.checks import dynamic_cooldown

from utils.checks import cooldown_5s
from utils.errors import CommandError

from ._abc import MixinMeta


class ContextMenu(MixinMeta):
    @dynamic_cooldown(cooldown_5s)
    async def store_user_context(self, interaction: Interaction, member: Member):

        store = self.bot.tree.get_command("store")
        if not store:
            raise CommandError("Store command not found")

        interaction.user = member or interaction.user
        await store.callback(self=self, interaction=interaction)

    @dynamic_cooldown(cooldown_5s)
    async def nightmarket_user_context(self, interaction: Interaction, member: Member):

        nightmarket = self.bot.tree.get_command("nightmarket")
        if not nightmarket:
            raise CommandError("Nightmarket command not found")

        interaction.user = member or interaction.user
        await nightmarket.callback(self=self, interaction=interaction)

    @dynamic_cooldown(cooldown_5s)
    async def point_user_context(self, interaction: Interaction, member: Member):

        point = self.bot.tree.get_command("point")
        if not point:
            raise CommandError("Point command not found")

        interaction.user = member or interaction.user
        await point.callback(self=self, interaction=interaction)
