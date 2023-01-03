import json
import logging
import os
from typing import Any, Dict, List, Mapping, Optional, Tuple, TypedDict, Union

import discord
from discord import app_commands
from discord.app_commands import Choice, Command, ContextMenu, Group, Parameter, TranslationContextLocation as TCL
from discord.ext import commands

__all__ = ('I18nGetText',)

Localizable = Union[Command, Group, ContextMenu, Parameter, Choice]

_log = logging.getLogger('i18n_get_text')

class OptionsLocale(TypedDict, total=False):
    name: str
    description: str
    choices: Dict[str, str]


class CommandLocalization(OptionsLocale, total=False):
    options: Dict[str, OptionsLocale]


class Internationalization(TypedDict, total=False):
    strings: Dict[str, str]
    app_commands: Dict[str, CommandLocalization]


class I18nGetText:

    __latest_command: Optional[Union[Command, Group, ContextMenu]] = None
    __latest_binding: Optional[commands.Cog] = None
    __latest_parameter: Optional[Parameter] = None

    def __init__(self, folder: str) -> None:
        self.folder = folder

    def load_from_file(self, locale: discord.Locale) -> Internationalization:
        fp = os.path.join(self.folder, str(locale))
        try:
            with open(fp + '.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _dump(self, locale: discord.Locale, data: Dict[str, Any]) -> None:
        fp = os.path.join(self.folder, str(locale))
        with open(fp + '.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

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

    async def get_i18n(
        self,
        cogs: Mapping[str, commands.Cog],
        excludes: Optional[List[str]] = None,
        only_public: bool = False,
        replace_text: bool = False,
        clear_file: bool = False,
        set_locale: Optional[Tuple[discord.Locale]] = None,
    ) -> None:

        _log.info('i18n.getting_text')

        for locale in discord.Locale:

            if set_locale is not None:
                if locale not in set_locale:
                    continue

            data = self.load_from_file(locale) if not clear_file else {}

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

            self._dump(locale, dict(app_commands=cog_payload))

        _log.info('i18n.get_text')
