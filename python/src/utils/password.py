"""Secure password generation for account registration."""

from __future__ import annotations

import secrets
import string


def generate_password(length: int = 16) -> str:
    """Generate a random password satisfying AWS Builder ID policy.

    Requirements: >= 1 uppercase, >= 1 lowercase, >= 1 digit, >= 1 special char.
    """
    special = "!@#$&"
    alphabet = string.ascii_letters + string.digits + special
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.isupper() for c in pwd)
            and any(c.islower() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in special for c in pwd)
        ):
            return pwd
