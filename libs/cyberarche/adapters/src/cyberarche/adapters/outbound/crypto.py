"""SecretBoxPort adapter: Fernet envelope encryption for stored credentials."""

from __future__ import annotations

import base64
import binascii
import hashlib

from cryptography.fernet import Fernet

# Reject trivially weak keys when deriving. A brute-forceable passphrase would
# undermine the envelope encryption of connector/OAuth secrets (audit F-016).
_MIN_SECRET_LENGTH = 32


def _looks_like_fernet_key(secret: str) -> bool:
    """A ready-made Fernet key is 32 urlsafe-base64 bytes (44-char string)."""
    try:
        return len(base64.urlsafe_b64decode(secret)) == 32
    except (binascii.Error, ValueError):
        return False


def _derive_key(secret: str) -> bytes:
    # Prefer a real 32-byte Fernet key verbatim; otherwise derive one, requiring
    # enough length that the single SHA-256 pass isn't a brute-force shortcut.
    if _looks_like_fernet_key(secret):
        return secret.encode()
    if len(secret) < _MIN_SECRET_LENGTH:
        raise ValueError(
            "connector encryption key must be a 32-byte urlsafe-base64 Fernet "
            f"key or at least {_MIN_SECRET_LENGTH} characters"
        )
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
