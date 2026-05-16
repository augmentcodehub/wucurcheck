from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.application.list_accounts_use_case import ListAccountsUseCase
from core.domain import StoredAccountRecord


@dataclass
class DummyRepository:
	records: list[StoredAccountRecord]
	calls: list[str]

	def list_accounts(self, provider_scope: str) -> list[StoredAccountRecord]:
		self.calls.append(provider_scope)
		return self.records


def test_list_accounts_use_case_returns_repository_records():
	records = [
		StoredAccountRecord(
			record_id='1',
			provider='wucur',
			name='Console User',
			username='alice@example.com',
			password='secret',
		),
	]
	repository = DummyRepository(records=records, calls=[])

	result = ListAccountsUseCase(repository).run(provider_scope='wucur')

	assert result.records == records
	assert repository.calls == ['wucur']
