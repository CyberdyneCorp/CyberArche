"""SecretBoxPort adapter: Fernet envelope encryption for stored credentials."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


class FernetSecretBox:
    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("connector encryption key must not be empty")
        self._fernet = Fernet(_derive_key(secret))

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        return self._fernet.decrypt(bytes(ciphertext)).decode()
