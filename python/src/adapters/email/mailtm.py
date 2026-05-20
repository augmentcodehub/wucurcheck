"""Mail.tm temporary email client — free API, rotating domains."""

from __future__ import annotations

import random
import string

import httpx

from adapters.email.base import EmailClient, EmailMessage

BASE_URL = "https://api.mail.tm"


class MailTmClient(EmailClient):
    """Temporary email via mail.tm API.

    Usage:
        client = MailTmClient()
        email = client.create_email()  # auto-generates random@domain
        messages = client.fetch_recent_messages()
    """

    def __init__(self) -> None:
        self._http = httpx.Client(timeout=30)
        self._token: str | None = None
        self._email: str | None = None
        self._password = "KiroReg" + "".join(random.choices(string.digits, k=6)) + "!"

    @property
    def email_address(self) -> str | None:
        return self._email

    def create_email(self, prefix: str | None = None) -> str | None:
        """Create a temporary email. Returns full address or None."""
        # Get available domain
        resp = self._http.get(f"{BASE_URL}/domains")
        if resp.status_code != 200:
            return None
        members = resp.json().get("hydra:member", resp.json())
        if not members:
            return None
        domain = members[0]["domain"]

        # Create account
        name = prefix or "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self._email = f"{name}@{domain}"

        resp = self._http.post(
            f"{BASE_URL}/accounts",
            json={"address": self._email, "password": self._password},
        )
        if resp.status_code != 201:
            return None

        # Get auth token
        resp = self._http.post(
            f"{BASE_URL}/token",
            json={"address": self._email, "password": self._password},
        )
        if resp.status_code != 200:
            return None
        self._token = resp.json()["token"]
        return self._email

    def fetch_recent_messages(self, limit: int = 50) -> list[EmailMessage]:
        if not self._token:
            return []
        resp = self._http.get(
            f"{BASE_URL}/messages",
            headers={"Authorization": f"Bearer {self._token}"},
        )
        if resp.status_code != 200:
            return []

        items = resp.json().get("hydra:member", [])
        messages: list[EmailMessage] = []
        for item in items[:limit]:
            # Fetch full message for body
            msg_id = item.get("id", "")
            body = item.get("text", "") or item.get("intro", "")
            if not body and msg_id:
                detail = self._http.get(
                    f"{BASE_URL}/messages/{msg_id}",
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                if detail.status_code == 200:
                    d = detail.json()
                    body = d.get("text", "") or d.get("html", [None])[0] or ""

            sender = item.get("from", {})
            messages.append(EmailMessage(
                id=msg_id,
                sender=sender.get("address", "") if isinstance(sender, dict) else str(sender),
                subject=item.get("subject", ""),
                body_text=body,
                received_at=item.get("createdAt", ""),
            ))
        return messages
