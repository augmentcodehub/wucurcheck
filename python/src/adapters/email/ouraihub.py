"""OurAIHub temporary email client (mail.ouraihub.com)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from adapters.email.base import EmailClient, EmailMessage

BASE_URL = 'https://mail.ouraihub.com/api'


@dataclass(frozen=True)
class OuraihubConfig:
    api_key: str
    domain: str = 'ouraihub.com'
    expiry_time: int = 3600000  # 1 hour


class OuraihubClient(EmailClient):
    """Temporary email via mail.ouraihub.com API.

    Usage:
        client = OuraihubClient(OuraihubConfig(api_key='mk_xxx'))
        client.create_email('myprefix')  # creates myprefix@moemail.app
        messages = client.fetch_recent_messages()
    """

    def __init__(self, config: OuraihubConfig):
        self._config = config
        self._http = httpx.Client(timeout=30)
        self._email_id: str | None = None
        self._email_address: str | None = None

    @property
    def headers(self) -> dict[str, str]:
        return {'X-API-Key': self._config.api_key}

    @property
    def email_address(self) -> str | None:
        return self._email_address

    def get_available_domains(self) -> list[str]:
        """Get available email domains from system config."""
        resp = self._http.get(f'{BASE_URL}/config', headers=self.headers)
        if resp.status_code != 200:
            return [self._config.domain]
        data = resp.json()
        # Try common response shapes
        if isinstance(data, dict):
            domains = data.get('domains') or data.get('data', {}).get('domains')
            if isinstance(domains, list):
                return domains
        return [self._config.domain]

    def create_email(self, name: str) -> str | None:
        """Generate a temporary email address. Returns the full email address."""
        resp = self._http.post(
            f'{BASE_URL}/emails/generate',
            headers={**self.headers, 'Content-Type': 'application/json'},
            json={
                'name': name,
                'expiryTime': self._config.expiry_time,
                'domain': self._config.domain,
            },
        )
        if resp.status_code not in (200, 201):
            return None
        data = resp.json()
        if isinstance(data, dict):
            self._email_id = data.get('id')
            self._email_address = data.get('email') or data.get('address')
            if not self._email_address and self._email_id:
                self._email_address = f'{name}@{self._config.domain}'
        return self._email_address

    def set_email_id(self, email_id: str) -> None:
        """Set email ID directly if already created."""
        self._email_id = email_id

    def fetch_recent_messages(self, limit: int = 50) -> list[EmailMessage]:
        if not self._email_id:
            return []
        resp = self._http.get(
            f'{BASE_URL}/emails/{self._email_id}',
            headers=self.headers,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()

        items = data.get('messages', []) if isinstance(data, dict) else []
        messages: list[EmailMessage] = []
        for item in items[:limit]:
            body = item.get('html') or item.get('content') or item.get('text') or ''
            messages.append(EmailMessage(
                id=str(item.get('id', '')),
                sender=item.get('from_address') or item.get('from') or '',
                subject=str(item.get('subject', '')),
                body_text=body,
                received_at=str(item.get('received_at') or item.get('sent_at') or ''),
            ))
        return messages

