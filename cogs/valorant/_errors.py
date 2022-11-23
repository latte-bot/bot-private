from utils.errors import CommandError


class NoAccountsLinked(CommandError):
    """You have no accounts linked"""

    pass


class InvalidMultiFactorCode(CommandError):
    """Invalid multi factor code"""

    pass
