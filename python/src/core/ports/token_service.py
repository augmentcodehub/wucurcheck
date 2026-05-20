"""Port: Token refresh service interface.

Abstracts token lifecycle management across different auth methods (OIDC, social, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.registration import TokenRefreshResult


class TokenService(ABC):
    """Abstract token refresh service."""

    @property
    @abstractmethod
    def auth_method(self) -> str:
        """Auth method identifier, e.g. 'oidc', 'social'."""

    @abstractmethod
    async def refresh(
        self,
        refresh_token: str,
        *,
        client_id: str = "",
        client_secret: str = "",
        region: str = "us-east-1",
    ) -> TokenRefreshResult:
        """Refresh an access token.

        Implementations MUST NOT raise — errors go into TokenRefreshResult.error.
        """
