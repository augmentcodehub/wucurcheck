"""Application use case for due-account batch check-in."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from core.domain import (
	CheckinDueSummary,
	CheckinSuccessUpdate,
	StoredAccountRecord,
	classify_due_accounts,
	resolve_as_of_date,
)


@dataclass(frozen=True)
class CheckinAccountResult:
	success: bool
	error_code: str | None
	message: str | None = None


@runtime_checkable
class CheckDueRunner(Protocol):
	repository: object

	def run_account_checkin(
		self,
		record: StoredAccountRecord,
		*,
		checkin_date: date | None = None,
	) -> tuple[CheckinAccountResult, CheckinSuccessUpdate | None]:
		...


class CheckDueAccountsUseCase:
	def __init__(self, runner: CheckDueRunner):
		self.runner = runner

	def run(
		self,
		*,
		as_of: str | None,
		timezone: str | None,
		dry_run: bool,
		provider_scope: str,
	) -> CheckinDueSummary:
		repository = self.runner.repository
		as_of_date = resolve_as_of_date(as_of, timezone)
		records = repository.list_accounts(provider_scope)
		due_items, skipped_items, invalid_items = classify_due_accounts(
			records,
			as_of_date,
			provider_scope=provider_scope,
		)

		if dry_run:
			exit_code = 0 if not invalid_items else 1
			return CheckinDueSummary(
				scanned=len(records),
				due=len(due_items),
				skipped=len(skipped_items),
				succeeded=0,
				failed=len(invalid_items),
				exit_code=exit_code,
				error_code='INVALID_DATE_FORMAT' if invalid_items else None,
			)

		succeeded = 0
		failed = len(invalid_items)
		error_code = 'INVALID_DATE_FORMAT' if invalid_items else None

		for item in due_items:
			result, update = self.runner.run_account_checkin(item.record, checkin_date=as_of_date)
			if result.success and update is not None:
				try:
					repository.save_checkin_success(item.record.record_id, update)
				except Exception:
					failed += 1
					error_code = 'BACKEND_WRITE_FAILED'
				else:
					succeeded += 1
			else:
				failed += 1
				error_code = result.error_code or error_code or 'CHECKIN_REQUEST_FAILED'

		exit_code = 0 if failed == 0 else 1
		return CheckinDueSummary(
			scanned=len(records),
			due=len(due_items),
			skipped=len(skipped_items),
			succeeded=succeeded,
			failed=failed,
			exit_code=exit_code,
			error_code=error_code,
		)
