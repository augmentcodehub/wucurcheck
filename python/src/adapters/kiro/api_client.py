"""Kiro Web Portal API client — CBOR-based RPC protocol.

Endpoint: https://app.kiro.dev/service/KiroWebPortalService/operation/{operation}
Protocol: rpc-v2-cbor (Smithy)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import cbor2
import httpx

log = logging.getLogger(__name__)

API_BASE = "https://app.kiro.dev/service/KiroWebPortalService/operation"


@dataclass
class KiroAccount:
    """Credentials needed to call Kiro API."""

    access_token: str
    idp: str = "BuilderId"  # BuilderId | Github | Google


@dataclass
class UsageInfo:
    """Parsed usage data from GetUserUsageAndLimits."""

    current: int = 0
    limit: int = 0
    base_current: int = 0
    base_limit: int = 0
    free_trial_current: int = 0
    free_trial_limit: int = 0
    free_trial_expiry: str | None = None
    bonuses: list[dict[str, Any]] = field(default_factory=list)
    next_reset_date: str | None = None


@dataclass
class AccountStatus:
    """Result of checking a Kiro account's status."""

    active: bool
    email: str | None = None
    user_id: str | None = None
    idp: str | None = None
    subscription_type: str = "Free"
    subscription_title: str = ""
    usage: UsageInfo = field(default_factory=UsageInfo)
    days_remaining: int | None = None
    error: str | None = None
    suspended: bool = False


class KiroApiError(Exception):
    """Raised when Kiro API returns an error."""

    def __init__(self, status_code: int, error_type: str = "", message: str = ""):
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(message or f"{error_type} (HTTP {status_code})")


class KiroApiClient:
    """Async client for Kiro Web Portal Service (CBOR protocol)."""

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    async def request(self, operation: str, body: dict, account: KiroAccount) -> dict:
        """Make a CBOR-encoded API request."""
        headers = {
            "accept": "application/cbor",
            "content-type": "application/cbor",
            "smithy-protocol": "rpc-v2-cbor",
            "amz-sdk-invocation-id": str(uuid.uuid4()),
            "amz-sdk-request": "attempt=1; max=1",
            "x-amz-user-agent": "aws-sdk-js/1.0.0 kiro-account-manager/1.0.0",
            "authorization": f"Bearer {account.access_token}",
            "cookie": f"Idp={account.idp}; AccessToken={account.access_token}",
        }

        encoded_body = cbor2.dumps(body)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{API_BASE}/{operation}",
                headers=headers,
                content=encoded_body,
            )

        if not resp.is_success:
            error_type, message = self._parse_error(resp)
            raise KiroApiError(resp.status_code, error_type, message)

        return cbor2.loads(resp.content)

    async def get_user_info(self, account: KiroAccount) -> dict:
        """GetUserInfo — returns email, userId, idp, status, featureFlags."""
        return await self.request("GetUserInfo", {"origin": "KIRO_IDE"}, account)

    async def get_usage(self, account: KiroAccount) -> dict:
        """GetUserUsageAndLimits — returns usage, subscription, reset date."""
        return await self.request(
            "GetUserUsageAndLimits",
            {"isEmailRequired": True, "origin": "KIRO_IDE"},
            account,
        )

    async def check_status(self, account: KiroAccount) -> AccountStatus:
        """Check account status: user info + usage in one call."""
        try:
            user_info, usage_raw = await self._parallel_fetch(account)
        except KiroApiError as e:
            if e.status_code == 423 or "Suspended" in e.error_type:
                return AccountStatus(
                    active=False, suspended=True, error=str(e)
                )
            return AccountStatus(active=False, error=str(e))

        return self._build_status(user_info, usage_raw)

    async def _parallel_fetch(self, account: KiroAccount) -> tuple[dict | None, dict]:
        """Fetch user info and usage in parallel."""
        import asyncio

        async def _safe_user_info():
            try:
                return await self.get_user_info(account)
            except Exception:
                return None

        user_info, usage = await asyncio.gather(
            _safe_user_info(),
            self.get_usage(account),
        )
        return user_info, usage

    def _build_status(self, user_info: dict | None, usage_raw: dict) -> AccountStatus:
        """Parse raw API responses into AccountStatus."""
        # Parse usage
        credit = None
        for item in usage_raw.get("usageBreakdownList", []):
            if item.get("resourceType") == "CREDIT":
                credit = item
                break

        base_limit = credit.get("usageLimit", 0) if credit else 0
        base_current = credit.get("currentUsage", 0) if credit else 0

        ft_limit = ft_current = 0
        ft_expiry = None
        ft_info = credit.get("freeTrialInfo") if credit else None
        if ft_info and ft_info.get("freeTrialStatus") == "ACTIVE":
            ft_limit = ft_info.get("usageLimit", 0)
            ft_current = ft_info.get("currentUsage", 0)
            ft_expiry = ft_info.get("freeTrialExpiry")

        bonuses = []
        for b in (credit.get("bonuses") or []) if credit else []:
            if b.get("status") == "ACTIVE" or b.get("usageLimit", 0) > 0:
                bonuses.append({
                    "code": b.get("bonusCode", ""),
                    "name": b.get("displayName", ""),
                    "current": b.get("currentUsage", 0),
                    "limit": b.get("usageLimit", 0),
                    "expires_at": b.get("expiresAt"),
                })

        total_limit = base_limit + ft_limit + sum(b["limit"] for b in bonuses)
        total_current = base_current + ft_current + sum(b["current"] for b in bonuses)

        # Subscription
        sub_info = usage_raw.get("subscriptionInfo", {})
        sub_title = sub_info.get("subscriptionTitle", "Free")
        sub_type = "Free"
        if "PRO" in sub_title.upper():
            sub_type = "Pro"
        elif "ENTERPRISE" in sub_title.upper():
            sub_type = "Enterprise"

        # Days remaining
        days = None
        reset_date = usage_raw.get("nextDateReset")
        if reset_date:
            from datetime import datetime, timezone
            try:
                reset_ts = datetime.fromisoformat(reset_date.replace("Z", "+00:00"))
                days = max(0, (reset_ts - datetime.now(timezone.utc)).days)
            except Exception:
                pass

        return AccountStatus(
            active=True,
            email=(usage_raw.get("userInfo") or {}).get("email") or (user_info or {}).get("email"),
            user_id=(usage_raw.get("userInfo") or {}).get("userId") or (user_info or {}).get("userId"),
            idp=(user_info or {}).get("idp"),
            subscription_type=sub_type,
            subscription_title=sub_title,
            usage=UsageInfo(
                current=total_current,
                limit=total_limit,
                base_current=base_current,
                base_limit=base_limit,
                free_trial_current=ft_current,
                free_trial_limit=ft_limit,
                free_trial_expiry=ft_expiry,
                bonuses=bonuses,
                next_reset_date=reset_date,
            ),
            days_remaining=days,
        )

    @staticmethod
    def _parse_error(resp: httpx.Response) -> tuple[str, str]:
        """Parse CBOR or text error response."""
        try:
            data = cbor2.loads(resp.content)
            error_type = data.get("__type", "").split("#")[-1] or f"HTTP{resp.status_code}"
            message = data.get("message", str(resp.status_code))
            return error_type, message
        except Exception:
            return f"HTTP{resp.status_code}", resp.text[:200]
