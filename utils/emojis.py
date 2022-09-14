import enum


class LatteEmoji(enum.Enum):

    latte_icon = '<:latte_icon:1000787979549294612>'
    member_icon = '<:member:1000792187790954557>'
    channel_icon = '<:channel:1000792689685582006>'
    cursor = '<a:cursor:1000791536906293390>'
    slash_command = '<:slash_command:1000791542858002535>'
    python = '<:python:1000791541301919896>'
    discord_py = '<:dpy:1000791538873409630>'
    stacia_dev = '<:stacia_dev:1000795736486719588>'

    @property
    def id(self) -> int:
        return int(self.value.split(':')[2][:-1])

    def __str__(self) -> str:
        return self.value
