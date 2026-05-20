"""AWS OIDC token refresh adapter."""

from __future__ import annotations

import logging

import httpx

from core.ports.token_service import TokenService
from core.registration import TokenRefreshResult

log = logging.getLogger(__name__)


class OidcTokenService(TokenService):
    """Refresh AWS OIDC tokens (used by Kiro accounts)."""

    @property
    def auth_method(self) -> str:
        return "oidc"

    async def refresh(
        self,
        refresh_token: str,
        *,
        client_id: str = "",
        client_secret: str = "",
        region: str = "us-east-1",
    ) -> TokenRefreshResult:
        url = f"https://oidc.{region}.amazonaws.com/token"
        payload = {
            "clientId": client_id,
            "clientSecret": client_secret,
            "refreshToken": refresh_token,
            "grantType": "refresh_token",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    return TokenRefreshResult(
                        success=False,
                        error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    )
                data = resp.json()
                return TokenRefreshResult(
                    success=True,
                    access_token=data["accessToken"],
                    refresh_token=data.get("refreshToken", refresh_token),
                    expires_in=data.get("expiresIn"),
                )
        except Exception as exc:
            log.exception("OIDC token refresh failed")
            return TokenRefreshResult(success=False, error=str(exc))
