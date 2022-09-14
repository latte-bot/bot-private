def bold(text: str) -> str:
    """Returns a bolded string"""
    return f"**{text}**"


def underline(text: str) -> str:
    """Returns an underlined string"""
    return f"__{text}__"


def strikethrough(text: str) -> str:
    """Returns a strikethrough string"""
    return f"~~{text}~~"


def spoiler(text: str) -> str:
    """Returns a spoiler string"""
    return f'||{text}||'


def italics(text: str) -> str:
    """Returns an italicized string"""
    return f"*{text}*"


def inline(text: str) -> str:
    """Returns an inline string"""
    if "`" in text:
        return f"``{text}``"
    else:
        return f"`{text}`"


def code_block(text: str, lang: str = '') -> str:
    """Returns a codeblock string"""
    return f"```{lang}\n{text}```"
