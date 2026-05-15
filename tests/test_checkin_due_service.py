from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.checkin_due_domain import CheckinSuccessUpdate, StoredAccountRecord
from scripts.checkin_due_service import CheckinAccountResult, CheckinDueService
from utils.config import ProviderConfig


@dataclass
class FakeRepository:
	records: list[StoredAccountRecord]
	saved: list[tuple[str, CheckinSuccessUpdate]]

	def list_accounts(self, provider_scope: str):
		return list(self.records)

	def save_checkin_success(self, record_id: str, update: CheckinSuccessUpdate) -> None:
		self.saved.append((record_id, update))

	def close(self) -> None:
		pass


class FakeService(CheckinDueService):
	def __init__(self, repository, provider_config, responses):
		super().__init__(repository, provider_config)
		self._responses = list(responses)

	def run_account_checkin(self, record, *, checkin_date=None):
		if not self._responses:
			raise AssertionError('unexpected run_account_checkin call')
		return self._responses.pop(0)


def _provider() -> ProviderConfig:
	return ProviderConfig(
		name='wucur',
		domain='http://wucur.com:6543',
		login_path='/login',
		login_api_path='/api/user/login',
		sign_in_path='/api/user/checkin',
		user_info_path='/api/user/self',
		api_user_key='new-api-user',
		auth_mode='password_session',
	)


def _records() -> list[StoredAccountRecord]:
	return [
		StoredAccountRecord(
			record_id='1',
			provider='wucur',
			name='A',
			username='a',
			password='p',
			checkin_date='2026-05-13',
		),
		StoredAccountRecord(
			record_id='2',
			provider='wucur',
			name='B',
			username='b',
			password='p',
			checkin_date='2026-05-14',
		),
	]


def test_run_dry_run_only_classifies():
	repository = FakeRepository(_records(), [])
	service = CheckinDueService(repository, _provider())

	summary = service.run(as_of='2026-05-14', timezone='Asia/Shanghai', dry_run=True)

	assert summary.scanned == 2
	assert summary.due == 1
	assert summary.skipped == 1
	assert summary.succeeded == 0
	assert summary.failed == 0
	assert summary.exit_code == 0
	assert repository.saved == []


def test_run_executes_success_and_writes_back():
	repository = FakeRepository(_records(), [])
	update = CheckinSuccessUpdate(checkin_date='2026-05-14', raw_result_json='{}')
	service = FakeService(
		repository,
		_provider(),
		[(CheckinAccountResult(True, None), update)],
	)

	summary = service.run(as_of='2026-05-14', timezone='Asia/Shanghai', dry_run=False)

	assert summary.scanned == 2
	assert summary.due == 1
	assert summary.skipped == 1
	assert summary.succeeded == 1
	assert summary.failed == 0
	assert summary.exit_code == 0
	assert repository.saved[0][0] == '1'
	assert repository.saved[0][1].checkin_date == '2026-05-14'


def test_run_counts_partial_failure():
	repository = FakeRepository(_records(), [])
	service = FakeService(
		repository,
		_provider(),
		[(CheckinAccountResult(False, 'CHECKIN_REQUEST_FAILED', 'boom'), None)],
	)

	summary = service.run(as_of='2026-05-14', timezone='Asia/Shanghai', dry_run=False)

	assert summary.succeeded == 0
	assert summary.failed == 1
	assert summary.exit_code == 1
	assert summary.error_code == 'CHECKIN_REQUEST_FAILED'
