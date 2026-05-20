"""Kiro Auth Service token refresh for social logins (GitHub/Google)."""

from __future__ import annotations

import logging

import httpx

from core.ports.token_service import TokenService
from core.registration import TokenRefreshResult

log = logging.getLogger(__name__)

KIRO_AUTH_ENDPOINT = "https://prod.us-east-1.auth.desktop.kiro.dev"


class SocialTokenService(TokenService):
    """Refresh tokens for social login accounts (GitHub/Google).

    Unlike OIDC (BuilderId), social login only needs the refreshToken — no clientId/clientSecret.
    """

    @property
    def auth_method(self) -> str:
        return "social"

    async def refresh(
        self,
        refresh_token: str,
        *,
        client_id: str = "",
        client_secret: str = "",
        region: str = "us-east-1",
    ) -> TokenRefreshResult:
        url = f"{KIRO_AUTH_ENDPOINT}/refreshToken"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    json={"refreshToken": refresh_token},
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "kiro-account-manager/1.0.0",
                    },
                )
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
            log.exception("Social token refresh failed")
            return TokenRefreshResult(success=False, error=str(exc))
