"""Use case: Batch refresh Kiro accounts — refresh tokens and check status in parallel."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from core.application.check_account_status_use_case import (
    AccountCredentials,
    CheckAccountStatusUseCase,
    StatusResult,
)

log = logging.getLogger(__name__)


@dataclass
class BatchAccount:
    """One account entry for batch processing."""

    id: str
    email: str
    credentials: AccountCredentials


@dataclass
class BatchResult:
    """Result of a single account in the batch."""

    id: str
    email: str
    result: StatusResult | None = None
    error: str | None = None


@dataclass
class BatchSummary:
    """Aggregate result of batch refresh."""

    total: int = 0
    success: int = 0
    failed: int = 0
    suspended: int = 0
    results: list[BatchResult] = field(default_factory=list)


class BatchRefreshUseCase:
    """Refresh and check status for multiple Kiro accounts with concurrency control."""

    def __init__(self, concurrency: int = 10) -> None:
        self._concurrency = concurrency
        self._use_case = CheckAccountStatusUseCase()

    async def execute(
        self,
        accounts: list[BatchAccount],
        on_progress: Any = None,
    ) -> BatchSummary:
        summary = BatchSummary(total=len(accounts))
        semaphore = asyncio.Semaphore(self._concurrency)

        async def _process(account: BatchAccount) -> BatchResult:
            async with semaphore:
                try:
                    result = await self._use_case.execute(account.credentials)
                    return BatchResult(id=account.id, email=account.email, result=result)
                except Exception as exc:
                    log.error("Batch refresh failed for %s: %s", account.email, exc)
                    return BatchResult(id=account.id, email=account.email, error=str(exc))

        tasks = [_process(acc) for acc in accounts]
        for coro in asyncio.as_completed(tasks):
            batch_result = await coro
            summary.results.append(batch_result)

            if batch_result.error:
                summary.failed += 1
            elif batch_result.result and batch_result.result.status.suspended:
                summary.suspended += 1
                summary.failed += 1
            elif batch_result.result and batch_result.result.status.active:
                summary.success += 1
            else:
                summary.failed += 1

            if on_progress:
                on_progress(len(summary.results), summary.total)

        return summary
