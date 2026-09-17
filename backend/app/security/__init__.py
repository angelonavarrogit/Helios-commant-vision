"""Security utilities: encryption, secrets handling, sanitization.

Enforces the controls described in docs/security.md and the always-on
directives in .kiro/steering/security.md.
"""

from app.security.encryption import EncryptionError, decrypt, encrypt, generate_key
from app.security.masking import mask_number, mask_numbers_in_text
from app.security.sanitization import detect_injection, sanitize

__all__ = [
    "EncryptionError",
    "decrypt",
    "detect_injection",
    "encrypt",
    "generate_key",
    "mask_number",
    "mask_numbers_in_text",
    "sanitize",
]
