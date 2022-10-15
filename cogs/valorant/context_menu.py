import discord
from discord import Interaction, Member, Message
from discord.app_commands.checks import dynamic_cooldown

from utils.checks import cooldown_5s
from utils.errors import CommandError

from ._abc import MixinMeta

# class PartyInviteModel(discord.ui.Modal):
#     def __init__(self, *args, **kwargs) -> None:
#         super().__init__(*args, **kwargs)
# self._selcect_account = discord.ui.Select()
# self.add_item()


class ContextMenu(MixinMeta):  # noqa
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

    @dynamic_cooldown(cooldown_5s)
    async def party_request_user_context(self, interaction: Interaction, member: Member):

        ...

    @dynamic_cooldown(cooldown_5s)
    async def party_request_message_context(self, interaction: Interaction, message: Message):

        await interaction.response.defer(ephemeral=True)

        riot_acc = await self.get_riot_account(user_id=interaction.user.id)
        if len(riot_acc) > 1:
            if len(riot_acc) == 1:
                client = await self.v_client.set_authorize(riot_acc[0])
                party = await client.http.party_fetch_player()
                if party is not None:
                    for display_name in message.content.split('\n'):
                        await party.invite_player(display_name)
            else:
                ...

        # for acc in riot_acc:
        #     client = await self.v_client.set_authorize(acc)
        #     party = await client.http.fetch_party_player()
        #     if party is not None:
        #         for display_name in message.content.split('\n'):
        #             await party.invite_player(display_name)
        #         break

        # party = await self.v_client.fetch_party_player()
        # for display_name in message.content.split('\n'):
        #     await party.invite_player(display_name)
        # await party.invite_by_display_name(display_name=message.content)
