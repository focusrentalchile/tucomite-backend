"""Password hashing. Verification can be added when sign-in checks the hash."""

import hashlib
import secrets


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash. The raw password is not stored."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000)
    return f"{salt}${digest.hex()}"
