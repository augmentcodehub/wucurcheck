"""Use case: Register an account via any provider.

Orchestrates provider selection, prerequisite validation, and transient-failure retry.
"""

from __future__ import annotations

import asyncio
import logging

from core.ports.registration_service import RegistrationConfig, RegistrationService
from core.registration import RegistrationResult

log = logging.getLogger(__name__)

TRANSIENT_KEYWORDS = ("timeout", "network", "browser crashed", "page closed", "connection")


class RegisterAccountUseCase:
    """Unified registration orchestrator. Provider-agnostic."""

    def __init__(self, services: dict[str, RegistrationService]) -> None:
        self._services = services

    @property
    def supported_providers(self) -> list[str]:
        return list(self._services.keys())

    async def execute(
        self,
        provider: str,
        email: str,
        config: RegistrationConfig | None = None,
        **kwargs: object,
    ) -> RegistrationResult:
        service = self._services.get(provider)
        if not service:
            return RegistrationResult(
                success=False,
                username=email,
                platform=provider,
                error=f"Unknown provider: {provider}. Supported: {self.supported_providers}",
            )

        err = service.validate_prerequisites(**kwargs)
        if err:
            return RegistrationResult(success=False, username=email, platform=provider, error=err)

        cfg = config or RegistrationConfig()
        return await self._execute_with_retry(service, email, cfg, **kwargs)

    async def _execute_with_retry(
        self,
        service: RegistrationService,
        email: str,
        config: RegistrationConfig,
        **kwargs: object,
    ) -> RegistrationResult:
        last_result: RegistrationResult | None = None

        for attempt in range(1 + config.max_retries):
            result = await service.register(email, config, **kwargs)
            if result.success:
                return result

            last_result = result

            if not self._is_transient(result.error):
                break

            if attempt < config.max_retries:
                log.warning(
                    "Transient failure (attempt %d/%d): %s",
                    attempt + 1,
                    config.max_retries,
                    result.error,
                    extra={"email": email, "provider": service.platform},
                )
                await asyncio.sleep(5)

        return last_result  # type: ignore[return-value]

    @staticmethod
    def _is_transient(error: str | None) -> bool:
        if not error:
            return False
        lower = error.lower()
        return any(kw in lower for kw in TRANSIENT_KEYWORDS)
