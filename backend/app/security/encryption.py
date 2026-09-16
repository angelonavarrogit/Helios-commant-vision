"""HELIOS — Encryption at rest for sensitive tokens (ADR-010).

Purpose
-------
OAuth refresh tokens let HELIOS read a mailbox over time. They are secrets and
must never be stored in clear text (steering §2). This module encrypts such
values before they touch the database and decrypts them only in memory when a
provider needs to authenticate.

Mechanism
---------
We use Fernet (from the ``cryptography`` package): AES-128 in CBC mode with an
HMAC-SHA256 authentication tag and a timestamp. Fernet is *authenticated*
encryption, so tampered ciphertext is rejected on decrypt rather than silently
producing garbage.

Key management
--------------
The symmetric key comes from the ``ENCRYPTION_KEY`` environment variable (a
url-safe base64 32-byte Fernet key). It is never hardcoded and never committed.
Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Rotation and per-record nonces are handled by Fernet internally; key rotation at
the operational level is covered in docs/operations.md.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class EncryptionError(RuntimeError):
    """Raised when encryption/decryption fails or the key is misconfigured."""


def _get_cipher() -> Fernet:
    """Build a Fernet cipher from the configured key.

    Raises :class:`EncryptionError` with a clear message when the key is missing
    or malformed, so misconfiguration fails fast and loud (never silently
    storing plaintext).
    """
    key = get_settings().encryption_key
    if not key:
        raise EncryptionError(
            "ENCRYPTION_KEY is not set. Generate one with "
            "Fernet.generate_key() and put it in your environment."
        )
    try:
        # Fernet expects bytes; accept the common str form from env.
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise EncryptionError("ENCRYPTION_KEY is not a valid Fernet key") from exc


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string, returning url-safe base64 ciphertext (str).

    The output is safe to store in a text column. Empty input is rejected to
    avoid accidentally persisting an "encrypted empty secret".
    """
    if plaintext == "":
        raise EncryptionError("refusing to encrypt an empty value")
    token = _get_cipher().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt(ciphertext: str) -> str:
    """Decrypt ciphertext produced by :func:`encrypt`, returning the plaintext.

    Raises :class:`EncryptionError` if the token is invalid or was tampered
    with (Fernet authentication failure).
    """
    try:
        plaintext = _get_cipher().decrypt(ciphertext.encode("ascii"))
    except (InvalidToken, ValueError, TypeError) as exc:
        raise EncryptionError("failed to decrypt value (invalid or tampered token)") from exc
    return plaintext.decode("utf-8")


def generate_key() -> str:
    """Return a fresh Fernet key (url-safe base64 str).

    Convenience for setup/tests. Operationally, generate once and store in the
    environment / secrets manager — never in git.
    """
    return Fernet.generate_key().decode("ascii")
