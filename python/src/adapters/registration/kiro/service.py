"""Kiro (AWS Builder ID) registration service adapter."""

from __future__ import annotations

import logging

from adapters.email.base import EmailClient
from core.ports.registration_service import RegistrationConfig, RegistrationService
from core.registration import Credentials, RegistrationResult, RegistrationStatus
from utils.password import generate_password

from .browser_flow import KiroBrowserFlow
from .sso_device_auth import sso_device_auth

log = logging.getLogger(__name__)


class KiroRegistrationService(RegistrationService):
    """Kiro registration: browser flow → sso_token → device auth → tokens."""

    def __init__(self, email_client: EmailClient) -> None:
        self._email_client = email_client

    @property
    def platform(self) -> str:
        return "kiro"

    def validate_prerequisites(self, **kwargs: object) -> str | None:
        if not self._email_client:
            return "Email client is required for Kiro registration"
        return None

    async def register(self, email: str, config: RegistrationConfig, **kwargs: object) -> RegistrationResult:
        password = config.password or generate_password()

        # Phase 1: Browser registration → sso_token
        flow = KiroBrowserFlow(
            email=email,
            password=password,
            email_client=self._email_client,
            config=config,
        )
        sso_token = await flow.execute()

        if not sso_token or sso_token.startswith("ERROR:"):
            error_msg = sso_token[6:] if sso_token else "Failed to get SSO Token"
            log.error("Browser flow failed for %s: %s", email, error_msg)
            return RegistrationResult(
                success=False,
                username=email,
                platform=self.platform,
                error=error_msg,
            )

        # Phase 2: SSO Device Auth → refreshToken + accessToken
        log.info("Starting SSO Device Auth for %s", email)
        auth_result = sso_device_auth(sso_token)

        credentials = Credentials(sso_token=sso_token)
        error = None

        if auth_result.get("success"):
            credentials.access_token = auth_result["accessToken"]
            credentials.refresh_token = auth_result["refreshToken"]
            credentials.client_id = auth_result["clientId"]
            credentials.client_secret = auth_result["clientSecret"]
            credentials.region = auth_result.get("region", "us-east-1")
            credentials.expires_in = auth_result.get("expiresIn")
        else:
            error = f"Device auth failed: {auth_result.get('error')} (sso_token still valid)"

        return RegistrationResult(
            success=True,
            username=email,
            password=password,
            platform=self.platform,
            status=RegistrationStatus.SUCCESS,
            name=flow.name,
            credentials=credentials,
            error=error,
        )
