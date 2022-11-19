from __future__ import annotations

from typing import TYPE_CHECKING

import discord.ui
from discord import Interaction, Member, Message, app_commands
from discord.app_commands import locale_str as _T
from discord.app_commands.checks import dynamic_cooldown

from utils.checks import cooldown_5s
from utils.errors import CommandError
from utils.views import ViewAuthor

from ._abc import MixinMeta

if TYPE_CHECKING:
    from ._database import ValorantUser


# class PartyInviteModel(discord.ui.Modal):
#     def __init__(self, *args, **kwargs) -> None:
#         super().__init__(*args, **kwargs)
# self._select_account = discord.ui.Select()
# self.add_item()

# class RequestPartyModel(discord.ui.Modal):
#
#     def __init__(self, *args, **kwargs) -> None:
#         super().__init__(*args, **kwargs)


class SelectRiotAuth(discord.ui.Select):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: Interaction) -> None:
        ...


class SelectRiotAuthView(ViewAuthor):
    def __init__(self, interaction: Interaction, v_user: ValorantUser) -> None:
        super().__init__(interaction)
        self.v_user = v_user
        self.add_item(SelectRiotAuth())


class ContextMenu(MixinMeta):  # noqa
    def __init__(self, *_args) -> None:
        super().__init__(*_args)
        self.ctx_user_store = app_commands.ContextMenu(
            name=_T('store'),
            callback=self.store_user_context,
        )
        self.ctx_user_party_request = app_commands.ContextMenu(
            name=_T('Party: Request to join'),
            callback=self.party_request_user_context,
        )
        self.ctx_message_party_invite = app_commands.ContextMenu(
            name=_T('Party: Invite'),
            callback=self.party_invite_message_context,
        )

        # self.context_user_nightmarket = app_commands.ContextMenu(
        #     name=_T('nightmarket'),
        #     callback=self.nightmarket_user_context,
        # )
        # self.context_user_point = app_commands.ContextMenu(
        #     name=_T('point'),
        #     callback=self.point_user_context,
        # )
        # self.ctx_user_party_invite = app_commands.ContextMenu(
        #     name=_T('party_invite'),
        #     callback=self.party_invite_user_context,
        # )
        # self.ctx_user_party_join = app_commands.ContextMenu(
        #     name=_T('party_join'),
        #     callback=self.party_join_user_context,
        # )
        # self.ctx_user_party_leave = app_commands.ContextMenu(
        #     name=_T('party_leave'),
        #     callback=self.party_leave_user_context
        # )
        # self.ctx_user_party_kick = app_commands.ContextMenu(
        #     name=_T('party_kick'),
        #     callback=self.party_kick_user_context
        # )

    @dynamic_cooldown(cooldown_5s)
    async def store_user_context(self, interaction: Interaction, member: Member):
        store = self.bot.tree.get_command("store")
        if not store:
            raise CommandError("Store command not found")

        interaction.user = member or interaction.user
        await store.callback(self=self, interaction=interaction)

    # party

    @dynamic_cooldown(cooldown_5s)
    async def party_request_user_context(self, interaction: Interaction, member: Member):
        ...
        # v_user = await self.fetch_user(id=member.id)
        # if len(v_user.get_riot_accounts()) > 1:
        #     view = SelectRiotAuthView(interaction, v_user)
        # else:
        #     client = await self.v_client.set_authorize(v_user.get_1st())
        #     party = await client.fetch_party()
        #     await self.invite_by_display_name(party, ...)

    @dynamic_cooldown(cooldown_5s)
    async def party_invite_message_context(self, interaction: Interaction, message: Message):
        ...

    # @dynamic_cooldown(cooldown_5s)
    # async def nightmarket_user_context(self, interaction: Interaction, member: Member):
    #
    #     nightmarket = self.bot.tree.get_command("nightmarket")
    #     if not nightmarket:
    #         raise CommandError("Nightmarket command not found")
    #
    #     interaction.user = member or interaction.user
    #     await nightmarket.callback(self=self, interaction=interaction)

    # @dynamic_cooldown(cooldown_5s)
    # async def point_user_context(self, interaction: Interaction, member: Member):
    #
    #     point = self.bot.tree.get_command("point")
    #     if not point:
    #         raise CommandError("Point command not found")
    #
    #     interaction.user = member or interaction.user
    #     await point.callback(self=self, interaction=interaction)

    # @dynamic_cooldown(cooldown_5s)
    # async def party_request_message_context(self, interaction: Interaction, message: Message):
    #
    #     await interaction.response.defer(ephemeral=True)
    #
    #     riot_auth = await self.fetch_user(id=interaction.user.id)
    #     if len(riot_auth.get_riot_accounts()) > 1:
    #         client = await self.v_client.set_authorize(riot_auth.get_1st())
    #         party = await client.fetch_party()
    #         if party is not None:
    #             for display_name in message.content.split('\n'):
    #                 await self.invite_by_display_name(party, display_name)

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
