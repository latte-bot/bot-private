from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import discord
from discord import Interaction, ui

from .i18n import _

if TYPE_CHECKING:
    ...

# original code from # https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/paginator.py


class NumberedPageModal(discord.ui.Modal, title='Go to page'):
    page = discord.ui.TextInput(label='Page', placeholder='Enter a number', min_length=1)

    def __init__(self, max_pages: Optional[int]) -> None:
        super().__init__()
        if max_pages is not None:
            as_string = str(max_pages)
            self.page.placeholder = f'Enter a number between 1 and {as_string}'
            self.page.max_length = len(as_string)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.interaction = interaction
        self.stop()


class PageSource:

    """An interface representing a menu page's data source for the actual menu page.
    Subclasses must implement the backing resource along with the following methods:
    - :meth:`get_page`
    - :meth:`is_paginating`
    - :meth:`format_page`
    """

    async def _prepare_once(self):
        try:
            # Don't feel like formatting hasattr with
            # the proper mangling
            # read this as follows:
            # if hasattr(self, '__prepare')
            # except that it works as you expect
            self.__prepare  # type: ignore
        except AttributeError:
            await self.prepare()
            self.__prepare = True

    async def prepare(self):
        """|coro|
        A coroutine that is called after initialisation
        but before anything else to do some asynchronous set up
        as well as the one provided in ``__init__``.
        By default this does nothing.
        This coroutine will only be called once.
        """
        return

    def is_paginating(self):
        """An abstract method that notifies the :class:`MenuPages` whether or not
        to start paginating. This signals whether to add reactions or not.
        Subclasses must implement this.
        Returns
        --------
        :class:`bool`
            Whether to trigger pagination.
        """
        raise NotImplementedError

    def get_max_pages(self) -> Optional[int]:
        """An optional abstract method that retrieves the maximum number of pages
        this page source has. Useful for UX purposes.
        The default implementation returns ``None``.
        Returns
        --------
        Optional[:class:`int`]
            The maximum number of pages required to properly
            paginate the elements, if given.
        """
        return None

    async def get_page(self, page_number: int) -> Any:
        """|coro|
        An abstract method that retrieves an object representing the object to format.
        Subclasses must implement this.
        .. note::
            The page_number is zero-indexed between [0, :meth:`get_max_pages`),
            if there is a maximum number of pages.
        Parameters
        -----------
        page_number: :class:`int`
            The page number to access.
        Returns
        ---------
        Any
            The object represented by that page.
            This is passed into :meth:`format_page`.
        """
        raise NotImplementedError

    async def format_page(self, menu: Any, page: Any) -> Union[discord.Embed, str, Dict[Any, Any]]:
        """|maybecoro|
        An abstract method to format the page.
        This method must return one of the following types.
        If this method returns a ``str`` then it is interpreted as returning
        the ``content`` keyword argument in :meth:`discord.Message.edit`
        and :meth:`discord.abc.Messageable.send`.
        If this method returns a :class:`discord.Embed` then it is interpreted
        as returning the ``embed`` keyword argument in :meth:`discord.Message.edit`
        and :meth:`discord.abc.Messageable.send`.
        If this method returns a ``dict`` then it is interpreted as the
        keyword-arguments that are used in both :meth:`discord.Message.edit`
        and :meth:`discord.abc.Messageable.send`. The two of interest are
        ``embed`` and ``content``.
        Parameters
        ------------
        menu: :class:`Menu`
            The menu that wants to format this page.
        page: Any
            The page returned by :meth:`PageSource.get_page`.
        Returns
        ---------
        Union[:class:`str`, :class:`discord.Embed`, :class:`dict`]
            See above.
        """
        raise NotImplementedError


class ListPageSource(PageSource):
    """A data source for a sequence of items.
    This page source does not handle any sort of formatting, leaving it up
    to the user. To do so, implement the :meth:`format_page` method.
    Attributes
    ------------
    entries: Sequence[Any]
        The sequence of items to paginate.
    per_page: :class:`int`
        How many elements are in a page.
    """

    def __init__(self, entries: List[Any], *, per_page: int):
        self.entries = entries
        self.per_page = per_page

        pages, left_over = divmod(len(entries), per_page)
        if left_over:
            pages += 1

        self._max_pages = pages

    def is_paginating(self) -> bool:
        """:class:`bool`: Whether pagination is required."""
        return len(self.entries) > self.per_page

    def get_max_pages(self) -> Optional[int]:
        """:class:`int`: The maximum number of pages required to paginate this sequence."""
        return self._max_pages

    async def get_page(self, page_number: int) -> List[Any]:
        """Returns either a single element of the sequence or
        a slice of the sequence.
        If :attr:`per_page` is set to ``1`` then this returns a single
        element. Otherwise it returns at most :attr:`per_page` elements.
        Returns
        ---------
        Union[Any, List[Any]]
            The data returned.
        """
        if self.per_page == 1:
            return self.entries[page_number]
        else:
            base = page_number * self.per_page
            return self.entries[base : base + self.per_page]


class LattePages(discord.ui.View):

    # def __init_subclass__(cls, *, multi_inherit: bool = False) -> None:
    #     ...

    if TYPE_CHECKING:
        _message: Optional[Union[discord.Message, discord.InteractionMessage]] = None

    def __init__(
        self,
        interaction: Optional[discord.Interaction] = None,
        source: Optional[PageSource] = None,
        check_embeds: bool = True,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.interaction = interaction
        self.source = source
        self.current_page = 0
        self.per_page = 1
        self.check_embeds = check_embeds
        self.fill_items()

    def fill_items(self) -> None:
        self.remove_item(self.numbered_page)

    def add_numbered_page(self, row: int = 1) -> None:
        self.numbered_page.row = row
        self.add_item(self.numbered_page)

    def _update_buttons(self) -> None:
        page = self.current_page
        max_pages = self.get_max_pages()
        if max_pages is not None:
            self.next_page.disabled = page == max_pages - 1
            self.last_page.disabled = page == max_pages - 1
        self.back_page.disabled = page == 0
        self.first_page.disabled = page == 0

    async def _get_kwargs_from_page(self, page) -> Dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {'content': value, 'embed': None}
        elif isinstance(value, discord.Embed):
            return {'embed': value, 'content': None}
        elif isinstance(value, list):
            return {'embeds': value, 'content': None}
        else:
            return {}

    def get_max_pages(self) -> Optional[int]:
        """:class:`int`: The maximum number of pages."""
        return self.source.get_max_pages()

    async def show_page(self, interaction: Interaction, page_number: 0) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        self._update_buttons()
        kwargs = await self._get_kwargs_from_page(page)
        if kwargs:
            if interaction.response.is_done():
                if hasattr(self, 'message'):
                    if self.message is not None:
                        await self.message.edit(**kwargs, view=self)
                else:
                    message = await interaction.response.followup(**kwargs, view=self)
                    self.message = message
            else:
                await interaction.response.edit_message(**kwargs, view=self)

    async def show_checked_page(self, interaction: Interaction, page_number: int):
        max_pages = self.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def start_pages(self, *, content: Optional[str] = None, ephemeral: bool = False) -> None:
        if self.check_embeds and not self.interaction.channel.permissions_for(self.interaction.guild.me).embed_links:
            await self.interaction.response.send_message(
                'Bot does not have embed links permission in this channel.', ephemeral=True
            )
            return

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)

        self._update_buttons()

        if content:
            kwargs.setdefault('content', content)
        if self.message is not None:
            await self.message.edit(**kwargs, view=self)
            return
        self.message = await self.interaction.followup.send(**kwargs, view=self, ephemeral=ephemeral)

    @property
    def message(self) -> Union[discord.Message, discord.Interaction]:
        if hasattr(self, '_message'):
            return self._message
        else:
            setattr(self, '_message', None)

    @message.setter
    def message(self, value: Union[discord.Message, discord.Interaction]) -> None:
        if hasattr(self, '_message'):
            self._message = value
        else:
            setattr(self, '_message', value)

    @ui.button(label='≪', custom_id='first_page')
    async def first_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, 0)

    @ui.button(label=_("Back"), style=discord.ButtonStyle.blurple, custom_id='back_page')
    async def back_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, self.current_page - 1)

    @ui.button(label=_("Next"), style=discord.ButtonStyle.blurple, custom_id='next_page')
    async def next_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, self.current_page + 1)

    @ui.button(label='≫', custom_id='last_page')
    async def last_page(self, interaction: Interaction, button: ui.Button):
        await self.show_checked_page(interaction, self.get_max_pages() - 1)

    @discord.ui.button(label='Skip to page...', style=discord.ButtonStyle.grey)
    async def numbered_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """lets you type a page number to go to"""
        if self.message is None:
            return

        modal = NumberedPageModal(self.source.get_max_pages())
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()

        if timed_out:
            await interaction.followup.send('Took too long', ephemeral=True)
            return
        elif self.is_finished():
            await modal.interaction.response.send_message('Took too long', ephemeral=True)
            return

        value = str(modal.page.value)
        if not value.isdigit():
            await modal.interaction.response.send_message(f'Expected a number not {value!r}', ephemeral=True)
            return

        value = int(value)
        await self.show_checked_page(modal.interaction, value - 1)
        if not modal.interaction.response.is_done():
            error = modal.page.placeholder.replace('Enter', 'Expected')  # type: ignore # Can't be None
            await modal.interaction.response.send_message(error, ephemeral=True)
