"""Application use case for listing accounts."""

from __future__ import annotations

from dataclasses import dataclass

from core.domain import StoredAccountRecord
from core.ports.account_repository import AccountRepository


@dataclass(frozen=True)
class ListAccountsResult:
	records: list[StoredAccountRecord]


class ListAccountsUseCase:
	def __init__(self, repository: AccountRepository):
		self.repository = repository

	def run(self, *, provider_scope: str) -> ListAccountsResult:
		records = self.repository.list_accounts(provider_scope)
		return ListAccountsResult(records=records)
