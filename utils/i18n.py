from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, TypedDict, Union

import discord
from discord import Locale, app_commands
from discord.app_commands import (
    Choice,
    Command,
    ContextMenu,
    Group,
    Parameter,
    TranslationContextLocation as TCL,
    locale_str,
)
from discord.ext import commands

if TYPE_CHECKING:
    from discord.app_commands import TranslationContext

    Localizable = Union[Command, Group, ContextMenu, Parameter, Choice]

_log = logging.getLogger('latte_bot.i18n')


class OptionsLocale(TypedDict, total=False):
    name: str
    description: str
    choices: Dict[str, str]


class CommandLocalization(OptionsLocale, total=False):
    options: Dict[str, OptionsLocale]


class Internationalization(TypedDict, total=False):
    strings: Dict[str, str]
    app_commands: Dict[str, CommandLocalization]


_translators: List[Translator] = []


class Translator(app_commands.Translator):

    # _localize_file = lru_cache(maxsize=1)(lambda self, locale: self._load_file(locale))
    _current_locale: discord.Locale = discord.Locale.american_english
    _translations: Dict[str, Any] = {str(locale): {} for locale in Locale}
    _strings: Dict[discord.Locale, Dict[str, Any]] = {locale: {} for locale in discord.Locale}

    _user_locale: Dict[int, discord.Locale] = {}

    def __init__(self, path: Optional[str] = None) -> None:
        super().__init__()
        self._path = path
        self.__latest_command: Optional[Union[Command, Group, ContextMenu]] = None
        self.__latest_binding: Optional[commands.Cog] = None
        self.__latest_parameter: Optional[Parameter] = None

        _translators.append(self)

    async def load(self) -> None:
        _log.info('i18n loaded')

    async def unload(self) -> None:
        _log.info('i18n unloaded')

    def __call__(self, untranslated: str) -> locale_str:
        return locale_str(untranslated)

    @staticmethod
    def _load_file(path: str, locale: Locale) -> Internationalization:
        filename = '{}.json'.format(locale)
        fp = os.path.join(path, filename)
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        else:
            return data

    @staticmethod
    def _dump_file(path: str, locale: Locale, data: Dict[str, Any]) -> None:
        filename = '{}.json'.format(locale)
        fp = os.path.join(path, filename)
        try:
            with open(fp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except FileNotFoundError:
            _log.warning(f'File {fp!r} not found')

    def set_locale(self, interaction: discord.Interaction) -> None:
        self._user_locale[interaction.user.id] = interaction.locale

    # def load_translations(self):
    #     """
    #     Loads the current translations.
    #     """
    #     locale = get_locale()
    #     if locale.lower() == "en-us":
    #         return
    #     if locale in self.translations:
    #         # Locales cannot be loaded twice as they have an entry in
    #         # self.translations
    #         return
    #     #
    #     # locale_path = get_locale_path(self.cog_folder, "po")
    #     # with contextlib.suppress(IOError, FileNotFoundError):
    #     #     with locale_path.open(encoding="utf-8") as file:
    #     #         self._parse(file)

    #
    # def _add_translation(self, untranslated, translated):
    #     untranslated = _unescape(untranslated)
    #     translated = _unescape(translated)
    #     if translated:
    #         self.translations[untranslated] = translated
    #
    # def _parse(self, key: str, translate: str):
    #     self._translations.update({key: translate})

    def _get_path(self) -> str:
        return self._path or os.path.join(os.getcwd(), 'i18n')

    @lru_cache(maxsize=30)
    def _localize_file(self, locale: Locale) -> Internationalization:
        path = self._get_path()
        return self._load_file(path, locale)

    def _localize_key(
        self, binding: Optional[Union[commands.Cog, str]], tcl: TCL, localizable: Localizable
    ) -> List[str]:

        keys = ['app_commands']

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

        elif tcl == TCL.parameter_name and (localizable, Parameter):
            keys.extend([localizable.command.name, 'parameters', localizable.name, 'name'])
            self.__latest_parameter = localizable

        elif tcl == TCL.parameter_description and isinstance(localizable, Parameter):
            keys.extend([localizable.command.name, 'parameters', localizable.name, 'description'])

        elif tcl == TCL.choice_name:
            if (
                self.__latest_command is not None
                and self.__latest_parameter is not None
                and isinstance(localizable, Choice)
            ):
                _choice_key = [
                    self.__latest_command.name,
                    'parameters',
                    self.__latest_parameter.name,
                    'choices',
                    localizable.value,
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
                for command in localizable.commands:
                    if isinstance(command, Command):
                        binding = command.binding
                        break
            elif localizable.module is not None:
                binding = localizable.module.removeprefix('cogs.')
        elif isinstance(localizable, Parameter):
            binding = localizable.command.binding
        elif isinstance(localizable, ContextMenu):
            ...
        elif isinstance(localizable, Choice):
            ...
        elif isinstance(localizable, str):
            ...

        localize_key = (
            self._localize_key(
                binding,
                tcl,
                localizable,
            )
            if tcl != TCL.other
            else ['strings', localizable]
        )

        def find_value_by_list_of_keys(fi18n: Internationalization, keys: List[str]) -> str:
            _string = fi18n
            for k in keys:
                try:
                    _string = _string[k]
                except KeyError:
                    return string.message

            if not isinstance(_string, str):
                _string = str(_string)

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
    async def get_i18n(
        cls,
        cogs: Mapping[str, commands.Cog],
        excludes: Optional[List[str]] = None,
        only_public: bool = False,
        replace_text: bool = False,
        clear: bool = False,
        set_locale: Optional[List[Locale]] = None,
    ) -> None:

        _log.info('i18n.getting_text')

        path = os.path.join(os.getcwd(), 'i18n')

        for locale in discord.Locale:

            if set_locale is not None:
                if locale not in set_locale:
                    continue

            if not clear:
                data = cls._load_file(path, locale)
            else:
                data = {}

            cog_payload = {}

            for cog in cogs.values():

                if excludes is not None:
                    excludes_lower = [x.lower() for x in excludes]
                    if cog.qualified_name.lower() in excludes_lower:
                        continue

                data_app_commands = data.get('app_commands', {})
                data_cog = data_app_commands.get(cog.qualified_name.lower(), {})

                app_cmd_payload = {}
                for app_cmd in cog.get_app_commands():

                    if only_public:
                        if app_cmd._guild_ids is not None:
                            continue

                    data_app_cmd = data_cog.get(app_cmd.name, {})

                    command_name = app_cmd.name if replace_text else data_app_cmd.get('name', app_cmd.name)
                    command_description = (
                        app_cmd.description if replace_text else data_app_cmd.get('description', app_cmd.description)
                    )

                    payload = {
                        'name': command_name,
                        'description': command_description,
                    }

                    if not isinstance(app_cmd, app_commands.Group):
                        if len(app_cmd.parameters) > 0:
                            payload_params = {}
                            for param in app_cmd.parameters:
                                param_name = (
                                    param.name
                                    if replace_text
                                    else data_app_cmd.get('parameters', {}).get(param.name, {}).get('name', param.name)
                                )
                                param_description = (
                                    param.description
                                    if replace_text
                                    else data_app_cmd.get('parameters', {})
                                    .get(param.name, {})
                                    .get('description', param.description)
                                )
                                params = {'name': param_name, 'description': param_description}
                                if len(param.choices) > 0:
                                    params['choices'] = {}
                                    for choice in param.choices:
                                        choice_name = (
                                            choice.name
                                            if replace_text
                                            else data_app_cmd.get('parameters', {})
                                            .get(param.name, {})
                                            .get('choices', {})
                                            .get(choice.name, {})
                                            .get('name', choice.name)
                                        )
                                        params['choices'][choice.value] = choice_name
                                payload_params[param.name] = params
                            payload['options'] = payload_params
                    app_cmd_payload[app_cmd.name] = payload

                if len(app_cmd_payload) > 0:
                    cog_payload[cog.qualified_name.lower()] = app_cmd_payload

            cls._dump_file(path, locale, dict(app_commands=cog_payload))

        _log.info('i18n.got_text')

    def load_string_localize(self) -> None:
        for locale in discord.Locale:
            data = self._load_file(os.path.join(os.getcwd(), 'i18n'), locale)
            strings = data.get('strings', {})
            for k, v in strings.items():
                self._strings[locale][k] = v

    @classmethod
    def get_string(
        cls,
        untranslate: str,
        locale: Optional[discord.Locale] = None,
        *,
        custom_id: Optional[str] = None,
    ) -> str:
        locale = locale or cls._current_locale
        key = custom_id or untranslate
        return cls._strings[locale].get(key, untranslate)


_: Callable[[str], str] = Translator.get_string
