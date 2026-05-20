"""Wucur registration service adapter — wraps existing wucur_client."""

from __future__ import annotations

import logging

import httpx

from adapters.http.wucur_client import register_account
from core.ports.registration_service import RegistrationConfig, RegistrationService
from core.registration import RegistrationResult, RegistrationStatus
from utils.password import generate_password

log = logging.getLogger(__name__)


class WucurRegistrationService(RegistrationService):
    """Wucur HTTP API registration."""

    @property
    def platform(self) -> str:
        return "wucur"

    def validate_prerequisites(self, **kwargs: object) -> str | None:
        password = kwargs.get("password") or None
        if not password:
            return None  # will auto-generate
        return None

    async def register(self, email: str, config: RegistrationConfig, **kwargs: object) -> RegistrationResult:
        raw_pw = kwargs.get("password")
        password = (str(raw_pw) if raw_pw else None) or config.password or generate_password()

        # Validate username length (wucur max = 20)
        if len(email) > 20:
            return RegistrationResult(
                success=False,
                username=email,
                platform=self.platform,
                error=f"Username too long ({len(email)} > 20 chars)",
            )

        try:
            with httpx.Client(timeout=30) as client:
                result = register_account(client, email, password)
        except Exception as exc:
            log.exception("Wucur registration HTTP error for %s", email)
            return RegistrationResult(
                success=False,
                username=email,
                platform=self.platform,
                error=f"HTTP error: {exc}",
            )

        if result.get("success"):
            log.info("Wucur registration succeeded: %s", email)
            return RegistrationResult(
                success=True,
                username=email,
                password=password,
                platform=self.platform,
                status=RegistrationStatus.SUCCESS,
            )

        error_msg = result.get("message", "Registration failed")
        log.warning("Wucur registration failed for %s: %s", email, error_msg)
        return RegistrationResult(
            success=False,
            username=email,
            platform=self.platform,
            error=error_msg,
        )
