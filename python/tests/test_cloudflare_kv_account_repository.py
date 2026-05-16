from __future__ import annotations

from pathlib import Path
import sys

import httpx

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.domain import CheckinSuccessUpdate, StoredAccountRecord
from adapters.persistence.sqlite.checkin_due_repository import CloudflareKvAccountRepository


class FakeResponse:
	def __init__(self, status_code: int, payload=None):
		self.status_code = status_code
		self._payload = payload or {}

	def json(self):
		return self._payload


class FakeClient:
	def __init__(self, records=None, status_code: int = 200):
		self.records = records or []
		self.status_code = status_code
		self.calls: list[tuple[str, str]] = []

	def request(self, method, url, headers=None, timeout=None, **kwargs):
		self.calls.append((method, url))
		if method == 'GET':
			return FakeResponse(self.status_code, self.records)
		return FakeResponse(self.status_code, {})

	def close(self):
		pass


def test_cloudflare_kv_repository_lists_accounts():
	client = FakeClient(
		records=[
			{
				'record_id': '1',
				'provider': 'wucur',
				'name': 'Console',
				'username': 'alice@example.com',
				'password': 'secret',
				'checkin_date': '2026-05-15',
			}
		]
	)
	repository = CloudflareKvAccountRepository('https://worker.example.com', 'secret', client=client)

	records = repository.list_accounts('wucur')

	assert len(records) == 1
	assert records[0].username == 'alice@example.com'


def test_cloudflare_kv_repository_saves_success():
	client = FakeClient()
	repository = CloudflareKvAccountRepository('https://worker.example.com', 'secret', client=client)

	repository.save_checkin_success('1', CheckinSuccessUpdate(checkin_date='2026-05-15'))

	assert client.calls[-1][0] == 'POST'
