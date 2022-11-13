from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING, Dict, List, Optional, TypedDict, Union

from discord import Locale, app_commands
from discord.app_commands import Choice, Command, ContextMenu, Group, Parameter, TranslationContextLocation as TCL
from discord.ext import commands

if TYPE_CHECKING:
    from discord.app_commands import TranslationContext, locale_str

    Localizable = Union[Command, Group, ContextMenu, Parameter, Choice]

_log = logging.getLogger('latte_bot.i18n')


class ParameterLocale(TypedDict, total=False):
    name: str
    description: str


class CommandLocalization(ParameterLocale, total=False):
    parameters: Dict[str, ParameterLocale]


class Internationalization(TypedDict, total=False):
    strings: Dict[str, str]
    commands: Dict[str, CommandLocalization]
    choices: Dict[str, str]


class Translator(app_commands.Translator):
    def __init__(self, path: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__path = path
        self.__latest_command: Optional[Union[Command, Group, ContextMenu]] = None
        self.__latest_binding: Optional[commands.Cog] = None
        self.__latest_parameter: Optional[Parameter] = None

    async def load(self) -> None:
        _log.info('i18n loaded')

    async def unload(self) -> None:
        _log.info('i18n unloaded')

    @lru_cache(maxsize=30)
    def _localize_file(self, locale: Locale) -> Internationalization:
        path = self.__path or os.path.join(os.getcwd(), 'locale')

        filename = f'{locale}.json'
        filepath = os.path.join(path, filename)

        try:
            with open(os.path.normpath(filepath), 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        else:
            _log.info(f'Loaded {locale!r} localization')
            return data

    def _localize_key(
        self, binding: Optional[Union[commands.Cog, str]], tcl: TCL, localizable: Localizable
    ) -> List[str]:

        if tcl == TCL.other:
            return ['strings', localizable.name]

        keys = ['commands']

        if binding is not None:
            if isinstance(binding, commands.Cog):
                keys.append(binding.qualified_name.lower())
            else:
                keys.append(binding.lower())

        if tcl in [TCL.command_name, TCL.group_name]:

            keys.extend([localizable.name, 'name'])

            self.__latest_command = localizable
            if binding is not None and isinstance(binding, commands.Cog):
                self.__latest_binding = binding

        elif tcl in [TCL.command_description, TCL.group_description]:
            keys.extend([localizable.name, 'description'])

        elif tcl == TCL.parameter_name:
            keys.extend([localizable.command.name, 'parameters', localizable.name, 'name'])
            self.__latest_parameter = localizable

        elif tcl == TCL.parameter_description:
            keys.extend([localizable.command.name, 'parameters', localizable.name, 'description'])

        elif tcl == TCL.choice_name:
            _choice_key = [
                self.__latest_command.name,
                'parameters',
                self.__latest_parameter.name,
                'choices',
                localizable.name,
            ]
            if self.__latest_binding is not None and isinstance(self.__latest_binding, commands.Cog):
                _choice_key.insert(0, self.__latest_binding.qualified_name.lower())
            keys.extend(_choice_key)

        return keys

    async def translate(self, string: locale_str, locale: Locale, context: TranslationContext) -> Optional[str]:
        localizable: Localizable = context.data
        tcl: TCL = context.location

        binding: Optional[Union[commands.Cog, str]] = None

        if isinstance(localizable, Command):
            binding = localizable.binding
        elif isinstance(localizable, Group):
            if len(localizable.commands) > 1:
                binding = localizable.commands[0].binding
            elif localizable.module is not None:
                binding = localizable.module.removeprefix('cogs.')
        elif isinstance(localizable, Parameter):
            binding = localizable.command.binding

        localize_key = (
            self._localize_key(
                binding,
                tcl,
                localizable,
            )
            if tcl != TCL.other
            else 'strings' + localizable.name
        )

        def find_value_by_list_of_keys(fi18n: Internationalization, keys: List[str]) -> str:
            _string = fi18n
            for k in keys:
                try:
                    _string = _string[k]
                except KeyError:
                    return string.message

            return _string

        localize_file = self._localize_file(locale)
        string_msg = find_value_by_list_of_keys(localize_file, localize_key)

        if tcl in [TCL.command_name, TCL.group_name]:
            string_msg = string_msg.lower()
            if not app_commands.commands.validate_name(string_msg):
                _log.warning(f'Invalid name for {string_msg!r} in {locale!r} ({tcl})')
                return None

        return string_msg

    @classmethod
    def get_text(cls, string: Union[locale_str, str], *, context: TranslationContext) -> str:
        if not isinstance(string, locale_str):
            string = locale_str(string)
        return string.message


_ = Translator.get_text
