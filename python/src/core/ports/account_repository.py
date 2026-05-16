"""Account repository port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.domain import CheckinSuccessUpdate, StoredAccountRecord


@runtime_checkable
class AccountRepository(Protocol):
	def list_accounts(self, provider_scope: str) -> list[StoredAccountRecord]:
		...

	def save_checkin_success(self, record_id: str, update: CheckinSuccessUpdate) -> None:
		...

	def close(self) -> None:
		...
