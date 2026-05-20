"""Use case: Check Kiro account status with automatic token refresh.

Flow: try API call → if 401, refresh token → retry → return status.
Dependencies injected via constructor — no hard-coded adapters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from adapters.kiro.api_client import AccountStatus, KiroAccount, KiroApiError
from core.registration import TokenRefreshResult

log = logging.getLogger(__name__)


class KiroApi(Protocol):
    """Port: Kiro API operations needed by this use case."""

    async def check_status(self, account: KiroAccount) -> AccountStatus: ...


class TokenRefresher(Protocol):
    """Port: Token refresh capability."""

    async def refresh(
        self,
        refresh_token: str,
        *,
        client_id: str = "",
        client_secret: str = "",
        region: str = "us-east-1",
    ) -> TokenRefreshResult: ...


@dataclass
class AccountCredentials:
    """Input credentials for status check."""

    access_token: str
    refresh_token: str
    client_id: str = ""
    client_secret: str = ""
    region: str = "us-east-1"
    auth_method: str = "oidc"  # "oidc" or "social"
    idp: str = "BuilderId"  # BuilderId | Github | Google


@dataclass
class StatusResult:
    """Output of status check, including refreshed credentials if applicable."""

    status: AccountStatus
    new_access_token: str | None = None
    new_refresh_token: str | None = None
    token_refreshed: bool = False


class CheckAccountStatusUseCase:
    """Check a Kiro account's status, auto-refreshing token if expired.

    Args:
        api: Kiro API client (implements KiroApi protocol).
        token_refreshers: Mapping of auth_method → TokenRefresher.
    """

    def __init__(
        self,
        api: KiroApi,
        token_refreshers: dict[str, TokenRefresher],
    ) -> None:
        self._api = api
        self._refreshers = token_refreshers

    async def execute(self, creds: AccountCredentials) -> StatusResult:
        account = KiroAccount(access_token=creds.access_token, idp=creds.idp)

        # First attempt
        try:
            status = await self._api.check_status(account)
            return StatusResult(status=status)
        except KiroApiError as e:
            if e.status_code == 423:
                return StatusResult(
                    status=AccountStatus(active=False, suspended=True, error=str(e))
                )
            if e.status_code != 401:
                return StatusResult(status=AccountStatus(active=False, error=str(e)))

        # Token expired — refresh and retry
        refresher = self._refreshers.get(creds.auth_method)
        if not refresher:
            return StatusResult(
                status=AccountStatus(
                    active=False,
                    error=f"No token refresher for auth_method={creds.auth_method}",
                )
            )

        log.info("Token expired, refreshing (method=%s)", creds.auth_method)
        refresh_result = await refresher.refresh(
            creds.refresh_token,
            client_id=creds.client_id,
            client_secret=creds.client_secret,
            region=creds.region,
        )

        if not refresh_result.success or not refresh_result.access_token:
            return StatusResult(
                status=AccountStatus(
                    active=False,
                    error=f"Token expired and refresh failed: {refresh_result.error}",
                )
            )

        # Retry with new token
        account = KiroAccount(access_token=refresh_result.access_token, idp=creds.idp)
        try:
            status = await self._api.check_status(account)
            return StatusResult(
                status=status,
                new_access_token=refresh_result.access_token,
                new_refresh_token=refresh_result.refresh_token,
                token_refreshed=True,
            )
        except KiroApiError as e:
            return StatusResult(status=AccountStatus(active=False, error=str(e)))
