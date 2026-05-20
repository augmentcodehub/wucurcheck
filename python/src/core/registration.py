"""Registration domain objects shared across all providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RegistrationStatus(Enum):
    """Account lifecycle status after registration attempt."""

    SUCCESS = "active"
    FAILED = "failed"
    SUSPENDED = "suspended"


@dataclass
class Credentials:
    """Provider-returned authentication credentials. Fields populated as needed."""

    sso_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    region: str = "us-east-1"
    expires_in: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize non-None fields for storage/callback."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class RegistrationResult:
    """Unified registration outcome returned by every provider adapter."""

    success: bool
    username: str = ""
    password: str = ""
    platform: str = ""
    status: RegistrationStatus = RegistrationStatus.FAILED
    name: str = ""
    credentials: Credentials = field(default_factory=Credentials)
    error: str | None = None

    def to_callback_dict(self) -> dict[str, Any]:
        """Convert to Worker batch_result item format for KV storage."""
        d: dict[str, Any] = {
            "username": self.username,
            "password": self.password,
            "platform": self.platform,
            "status": self.status.value,
            "last_result": "注册成功" if self.success else f"注册失败: {self.error}",
            "name": self.name,
        }
        d.update(self.credentials.to_dict())
        return d


@dataclass
class TokenRefreshResult:
    """Result of a token refresh operation."""

    success: bool
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    error: str | None = None
