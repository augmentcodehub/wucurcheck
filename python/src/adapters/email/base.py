"""Email client abstraction for verification code retrieval."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    id: str
    sender: str
    subject: str
    body_text: str
    received_at: str


class EmailClient(ABC):
    """Abstract base for fetching emails from any provider."""

    @abstractmethod
    def fetch_recent_messages(self, limit: int = 50) -> list[EmailMessage]:
        """Return recent messages, newest first."""
        ...
