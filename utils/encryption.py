import json
from typing import AnyStr

from cryptography.fernet import Fernet


class Encryption:
    """Encryption class."""

    _key: AnyStr

    def __init__(self, key: AnyStr) -> None:
        """Encryption class."""
        Encryption._key = key

    @staticmethod
    def encrypt(args: str) -> str:
        """Encrypts a message with the key."""
        return str(Fernet(Encryption._key).encrypt(args.encode())).split("'")[1]

    @staticmethod
    def decrypt(token: str) -> str:
        """Decrypts a message with the key."""
        return Fernet(Encryption._key).decrypt(bytes(token, "utf-8")).decode()

    @staticmethod
    def decrypt_to_dict(token: str) -> dict:
        """Decrypts a message with the key and returns a dict."""
        return json.loads(Encryption.decrypt(token))
