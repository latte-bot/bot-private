from typing import AnyStr

from cryptography.fernet import Fernet


class Encryption:
    """Encryption class."""

    def __init__(self, key: AnyStr) -> None:
        self.__key: AnyStr = key

    def encrypt(self, args: str) -> str:
        """Encrypts a message with the key."""
        return str(Fernet(self.__key).encrypt(args.encode())).split("'")[1]

    def decrypt(self, token: str) -> str:
        """Decrypts a message with the key."""
        return Fernet(self.__key).decrypt(bytes(token, "utf-8")).decode()
