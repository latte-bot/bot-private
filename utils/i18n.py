import contextlib
import io
import logging
import os
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Optional, Union

import discord
from discord import app_commands

if TYPE_CHECKING:
    from discord import Locale
    from discord.app_commands import TranslationContext, locale_str

_log = logging.getLogger('utils.i18n')


class Translator(app_commands.Translator):
    async def load(self) -> None:
        _log.info('lattebot i18n loaded')

    async def unload(self) -> None:
        _log.info('lattebot i18n unloaded')

    async def translate(
        self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext
    ) -> Optional[str]:
        # print(string, string.extras)
        if locale == discord.Locale.thai:

            # command name
            if string.message == 'login':
                return 'เข้าสู่ระบบ'
            if string.message == 'logout':
                return 'ออกจากระบบ'
            if string.message == 'store':
                return 'ร้านค้า'

            # command describe
            if string.message == 'Input username':
                return 'กรุณากรอกชื่อผู้ใช้'
            if string.message == 'Input password':
                return 'กรุณากรอกรหัสผ่าน'

            # command description
            if string.message == 'Log in with your Riot accounts':
                return 'เข้าสู่ระบบด้วยบัญชี Riot'

        return None


_translators = []

_current_locale = ContextVar("_current_locale", default="en-US")


def get_locale() -> str:
    return str(_current_locale.get())


def set_locale(locale: str) -> None:
    global _current_locale
    _current_locale = ContextVar("_current_locale", default=locale)
    reload_locales()


def set_interaction_locale(locale: Optional[str]) -> None:
    _current_locale.set(locale)
    reload_locales()


def reload_locales() -> None:
    for translator in _translators:
        translator.load_translations()


def _parse(translation_file: io.TextIOWrapper) -> Dict[str, str]:
    """
    Custom gettext parsing of translation files.
    Parameters
    ----------
    translation_file : io.TextIOWrapper
        An open text file containing translations.
    Returns
    -------
    Dict[str, str]
        A dict mapping the original strings to their translations. Empty
        translated strings are omitted.
    """
    step = None
    untranslated = ""
    translated = ""
    translations = {}
    locale = get_locale()

    translations[locale] = {}

    for line in translation_file:
        line = line.strip()

    #     if line.startswith(MSGID):
    #         # New msgid
    #         if step is IN_MSGSTR and translated:
    #             # Store the last translation
    #             translations[locale][_unescape(untranslated)] = _unescape(translated)
    #         step = IN_MSGID
    #         untranslated = line[len(MSGID): -1]
    #
    #     elif line.startswith('"') and line.endswith('"'):
    #         if step is IN_MSGID:
    #             # Line continuing on from msgid
    #             untranslated += line[1:-1]
    #         elif step is IN_MSGSTR:
    #             # Line continuing on from msgstr
    #             translated += line[1:-1]
    #     elif line.startswith(MSGSTR):
    #         # New msgstr
    #         step = IN_MSGSTR
    #         translated = line[len(MSGSTR): -1]
    #
    # if step is IN_MSGSTR and translated:
    #     # Store the final translation
    #     translations[locale][_unescape(untranslated)] = _unescape(translated)

    return translations


def _unescape(string):
    string = string.replace(r"\\", "\\")
    string = string.replace(r"\t", "\t")
    string = string.replace(r"\r", "\r")
    string = string.replace(r"\n", "\n")
    string = string.replace(r"\"", '"')
    return string


def get_locale_path(cog_folder: Path, extension: str) -> Path:
    """
    Gets the folder path containing localization files.
    :param Path cog_folder:
        The cog folder that we want localizations for.
    :param str extension:
        Extension of localization files.
    :return:
        Path of possible localization file, it may not exist.
    """
    return cog_folder / "locales" / "{}.{}".format(get_locale(), extension)


class TranslatorBot(Callable[[str], str]):
    """Function to get translated strings at runtime."""

    def __init__(self, name: str, file_location: Union[str, Path, os.PathLike]):
        """
        Initializes an internationalization object.
        Parameters
        ----------
        name : str
            Your cog name.
        file_location : `str` or `pathlib.Path`
            This should always be ``__file__`` otherwise your localizations
            will not load.
        """
        self.cog_folder = Path(file_location).resolve().parent
        self.cog_name = name
        self.translations = {}

        _translators.append(self)

        self.load_translations()

    def __call__(self, untranslated: str) -> str:
        """Translate the given string.
        This will look for the string in the translator's :code:`.pot` file,
        with respect to the current locale.
        """
        locale = get_locale()
        try:
            return self.translations[locale][untranslated]
        except KeyError:
            return untranslated

    def load_translations(self):
        """
        Loads the current translations.
        """
        locale = get_locale()
        if locale.lower() == "en-us":
            # Red is written in en-US, no point in loading it
            return
        if locale in self.translations:
            # Locales cannot be loaded twice as they have an entry in
            # self.translations
            return

        locale_path = get_locale_path(self.cog_folder, "po")
        with contextlib.suppress(IOError, FileNotFoundError):
            with locale_path.open(encoding="utf-8") as file:
                self._parse(file)

    def _parse(self, translation_file):
        self.translations.update(_parse(translation_file))

    def _add_translation(self, untranslated, translated):
        untranslated = _unescape(untranslated)
        translated = _unescape(translated)
        if translated:
            self.translations[untranslated] = translated


# This import to be down here to avoid circular import issues.
# This will be cleaned up at a later date
# noinspection PyPep8
from discord.app_commands import Command, ContextMenu, Group


def cog_i18n(translator: TranslatorBot):
    """Get a class decorator to link the translator to this cog."""

    def decorator(cog_class: type):
        cog_class.__translator__ = translator
        for name, attr in cog_class.__dict__.items():
            if isinstance(attr, (Command, ContextMenu, Group)):
                attr.translator = translator
                setattr(cog_class, name, attr)
        return cog_class

    return decorator
