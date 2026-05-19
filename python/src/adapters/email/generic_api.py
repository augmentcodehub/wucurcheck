"""Generic HTTP API email client — adapts any REST mail service via field mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import reduce

import httpx

from adapters.email.base import EmailClient, EmailMessage


@dataclass(frozen=True)
class GenericApiConfig:
    """Configuration for a generic email API endpoint."""
    api_url: str
    api_key: str = ''
    method: str = 'GET'
    extra_headers: dict[str, str] = field(default_factory=dict)
    # JSONPath-like dot notation for response parsing
    messages_path: str = 'data'
    id_field: str = 'id'
    sender_field: str = 'from'
    subject_field: str = 'subject'
    body_field: str = 'body'
    time_field: str = 'received_at'


def _resolve(obj: object, path: str) -> str:
    """Resolve a dot-separated path on a nested dict."""
    try:
        return str(reduce(lambda o, k: o[k] if isinstance(o, dict) else '', path.split('.'), obj))  # type: ignore[arg-type]
    except (KeyError, TypeError, IndexError):
        return ''


class GenericApiClient(EmailClient):
    """Fetch emails from any REST API using configurable field mapping."""

    def __init__(self, config: GenericApiConfig):
        self._config = config

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        for k, v in self._config.extra_headers.items():
            headers[k] = v.replace('{api_key}', self._config.api_key)
        if not headers and self._config.api_key:
            headers['Authorization'] = f'Bearer {self._config.api_key}'
        return headers

    def fetch_recent_messages(self, limit: int = 50) -> list[EmailMessage]:
        try:
            resp = httpx.request(
                self._config.method,
                self._config.api_url,
                headers=self._build_headers(),
                params={'limit': limit},
                timeout=30,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
        except Exception:
            return []

        # Navigate to messages list
        items = data
        if self._config.messages_path:
            for key in self._config.messages_path.split('.'):
                if isinstance(items, dict):
                    items = items.get(key, [])
                else:
                    return []
        if not isinstance(items, list):
            return []

        messages: list[EmailMessage] = []
        for item in items[:limit]:
            messages.append(EmailMessage(
                id=_resolve(item, self._config.id_field),
                sender=_resolve(item, self._config.sender_field),
                subject=_resolve(item, self._config.subject_field),
                body_text=_resolve(item, self._config.body_field),
                received_at=_resolve(item, self._config.time_field),
            ))
        return messages
