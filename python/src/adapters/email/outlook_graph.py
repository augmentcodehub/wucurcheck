"""Microsoft Graph API email client for Outlook."""

from __future__ import annotations

import httpx

from adapters.email.base import EmailClient, EmailMessage
from adapters.email.code_extractor import html_to_text

TOKEN_ENDPOINTS = [
    'https://login.microsoftonline.com/consumers/oauth2/v2.0/token',
    'https://login.microsoftonline.com/common/oauth2/v2.0/token',
]
GRAPH_MESSAGES_URL = 'https://graph.microsoft.com/v1.0/me/messages'


class OutlookGraphClient(EmailClient):
    """Fetch emails via Microsoft Graph API using OAuth2 refresh_token."""

    def __init__(self, refresh_token: str, client_id: str):
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._access_token: str | None = None

    def _refresh_access_token(self) -> str | None:
        for endpoint in TOKEN_ENDPOINTS:
            try:
                resp = httpx.post(
                    endpoint,
                    data={
                        'client_id': self._client_id,
                        'refresh_token': self._refresh_token,
                        'grant_type': 'refresh_token',
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=30,
                )
                if resp.status_code == 200:
                    self._access_token = resp.json()['access_token']
                    return self._access_token
            except Exception:
                continue
        return None

    def fetch_recent_messages(self, limit: int = 50) -> list[EmailMessage]:
        token = self._refresh_access_token()
        if not token:
            return []
        try:
            resp = httpx.get(
                GRAPH_MESSAGES_URL,
                params={
                    '$top': str(limit),
                    '$orderby': 'receivedDateTime desc',
                    '$select': 'id,subject,from,receivedDateTime,body',
                },
                headers={'Authorization': f'Bearer {token}'},
                timeout=30,
            )
            if resp.status_code != 200:
                return []
        except Exception:
            return []

        messages: list[EmailMessage] = []
        for item in resp.json().get('value', []):
            body_content = item.get('body', {}).get('content', '')
            messages.append(EmailMessage(
                id=item.get('id', ''),
                sender=item.get('from', {}).get('emailAddress', {}).get('address', ''),
                subject=item.get('subject', ''),
                body_text=html_to_text(body_content) or body_content,
                received_at=item.get('receivedDateTime', ''),
            ))
        return messages
