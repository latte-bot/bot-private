from enum import Enum, IntEnum
from typing import Tuple


class Theme(IntEnum):
    primacy = 0xFFFFFF
    secondary = 0x111111
    tertiary = 0x222222
    purple = 0xC0AEE0
    dark_purple = 0x8B7DB5
    gold = 0xF1B82D
    dark = 0x0F1923
    error = 0xFE676E

    def to_rgb(self) -> Tuple[int, int, int]:
        return self._value_ >> 16, self._value_ >> 8 & 0xFF, self._value_ & 0xFF
