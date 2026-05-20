"""Port: Registration service interface.

Each provider (kiro, wucur, cursor, ...) implements this contract.
The UseCase layer depends only on this abstraction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.registration import RegistrationResult


@dataclass
class RegistrationConfig:
    """Shared registration configuration passed to every provider."""

    proxy_url: str | None = None
    headless: bool = True
    code_timeout: int = 120
    max_retries: int = 2
    password: str | None = None  # None → auto-generate


class RegistrationService(ABC):
    """Abstract registration service. One implementation per provider."""

    @property
    @abstractmethod
    def platform(self) -> str:
        """Provider identifier, e.g. 'kiro', 'wucur'."""

    @abstractmethod
    async def register(
        self, email: str, config: RegistrationConfig, **kwargs: object
    ) -> RegistrationResult:
        """Execute a single account registration.

        Implementations MUST NOT raise — all errors are captured in
        RegistrationResult.error.
        """

    def validate_prerequisites(self, **kwargs: object) -> str | None:
        """Pre-flight check before registration.

        Returns:
            None if all prerequisites are met, otherwise an error message.
        """
        return None
