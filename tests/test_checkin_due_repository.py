from __future__ import annotations

from pathlib import Path
import sys

import httpx

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.account_registry_db import connect_db, ensure_schema, upsert_registered_account
from scripts.checkin_due_domain import CheckinSuccessUpdate
from scripts.checkin_due_repository import (
	CheckinDueAuthError,
	CheckinDueConfigurationError,
	CheckinDueUnavailableError,
	SqliteCheckinDueRepository,
	WorkerCheckinDueRepository,
	build_backend_repository,
)


def _create_temp_db(tmp_path: Path) -> Path:
	db_path = tmp_path / 'checkin_due.sqlite3'
	conn = connect_db(db_path)
	try:
		ensure_schema(conn)
		upsert_registered_account(
			conn,
			name='Console User',
			provider='wucur',
			username='alice@example.com',
			password='secret',
			registered_at='2026-05-13T10:00:00',
			checkin_date='2026-05-13',
			balance_before=1.0,
			balance_after=1.5,
			balance_delta=0.5,
			used_quota_before=0.2,
			used_quota_after=0.3,
			checkin_reward_raw=123,
			last_status='checkin_success',
			raw_result_json='{}',
		)
	finally:
		conn.close()
	return db_path


def test_sqlite_repository_lists_accounts_and_writes_success(tmp_path):
	db_path = _create_temp_db(tmp_path)

	repository = SqliteCheckinDueRepository(db_path)
	try:
		records = repository.list_accounts('wucur')
		assert len(records) == 1
		assert records[0].username == 'alice@example.com'

		update = CheckinSuccessUpdate(checkin_date='2026-05-14', raw_result_json='{"success":true}')
		repository.save_checkin_success(records[0].record_id, update)
	finally:
		repository.close()

	conn = connect_db(db_path)
	try:
		row = conn.execute('SELECT checkin_date, raw_result_json FROM registered_accounts WHERE username = ?', ('alice@example.com',)).fetchone()
	finally:
		conn.close()

	assert row['checkin_date'] == '2026-05-14'
	assert row['raw_result_json'] == '{"success":true}'


def test_sqlite_repository_rejects_missing_database(tmp_path):
	missing_path = tmp_path / 'missing.sqlite3'

	try:
		SqliteCheckinDueRepository(missing_path)
	except FileNotFoundError:
		assert True
	else:
		raise AssertionError('expected FileNotFoundError')


def test_worker_repository_requires_credentials():
	try:
		WorkerCheckinDueRepository('', 'token')
	except CheckinDueConfigurationError:
		assert True
	else:
		raise AssertionError('expected CheckinDueConfigurationError')


def test_worker_repository_maps_auth_failure():
	class FakeResponse:
		def __init__(self, status_code: int):
			self.status_code = status_code

		def json(self):
			return []

	class FakeClient:
		def request(self, method, url, headers=None, timeout=None, **kwargs):
			return FakeResponse(403)

		def close(self):
			pass

	repository = WorkerCheckinDueRepository('https://worker.example.com', 'secret', client=FakeClient())

	try:
		repository.list_accounts('wucur')
	except CheckinDueAuthError:
		assert True
	else:
		raise AssertionError('expected CheckinDueAuthError')


def test_worker_repository_maps_unavailable_failure():
	class FakeClient:
		def request(self, method, url, headers=None, timeout=None, **kwargs):
			raise httpx.ConnectError('boom', request=httpx.Request(method, url))

		def close(self):
			pass

	repository = WorkerCheckinDueRepository('https://worker.example.com', 'secret', client=FakeClient())

	try:
		repository.list_accounts('wucur')
	except CheckinDueUnavailableError:
		assert True
	else:
		raise AssertionError('expected CheckinDueUnavailableError')


def test_build_backend_repository_switches_backend(tmp_path):
	db_path = _create_temp_db(tmp_path)
	sqlite_repository = build_backend_repository('sqlite', db_path=db_path)
	try:
		assert sqlite_repository.list_accounts('wucur')
	finally:
		sqlite_repository.close()

	class FakeClient:
		def request(self, method, url, headers=None, timeout=None, **kwargs):
			class Response:
				status_code = 200

				@staticmethod
				def json():
					return []

			return Response()

		def close(self):
			pass

	worker_repository = build_backend_repository(
		'worker',
		worker_url='https://worker.example.com',
		worker_token='secret',
		client=FakeClient(),
	)
	try:
		assert worker_repository.list_accounts('wucur') == []
	finally:
		worker_repository.close()
