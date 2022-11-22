import json
from typing import AnyStr, Optional

from cryptography.fernet import Fernet


class Encryption:
    """Encryption class."""

    _key: AnyStr

    def __init__(self, key: Optional[AnyStr]) -> None:
        """Encryption class."""
        if key is None:
            raise ValueError('Encryption key is not set.')
        Encryption._key = key

    @staticmethod
    def encrypt(args: str) -> AnyStr:
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
