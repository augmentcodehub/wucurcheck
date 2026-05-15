#!/usr/bin/env python3
"""
Repository adapters for the checkin-due workflow.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx

from .account_registry_db import DEFAULT_DB_PATH, connect_db, ensure_schema
from .checkin_due_domain import CheckinSuccessUpdate, StoredAccountRecord


CHECKIN_DUE_PROVIDER = 'wucur'
WORKER_ACCOUNTS_PATH = '/v1/checkin/accounts'


class CheckinDueError(RuntimeError):
	pass


class CheckinDueConfigurationError(CheckinDueError):
	pass


class CheckinDueAuthError(CheckinDueError):
	pass


class CheckinDueUnavailableError(CheckinDueError):
	pass


@runtime_checkable
class CheckinDueRepository(Protocol):
	def list_accounts(self, provider_scope: str) -> list[StoredAccountRecord]:
		...

	def save_checkin_success(self, record_id: str, update: CheckinSuccessUpdate) -> None:
		...

	def close(self) -> None:
		...


def _record_from_row(row: sqlite3.Row) -> StoredAccountRecord:
	return StoredAccountRecord(
		record_id=str(row['id']),
		provider=str(row['provider']),
		name=str(row['name']),
		username=str(row['username']),
		password=str(row['password']),
		registered_at=row['registered_at'],
		checkin_date=row['checkin_date'],
		balance_before=row['balance_before'],
		balance_after=row['balance_after'],
		balance_delta=row['balance_delta'],
		used_quota_before=row['used_quota_before'],
		used_quota_after=row['used_quota_after'],
		checkin_reward_raw=row['checkin_reward_raw'],
		last_status=row['last_status'],
		raw_result_json=row['raw_result_json'],
	)


def _record_from_mapping(data: dict) -> StoredAccountRecord:
	record_id = data.get('record_id', data.get('id'))
	if record_id is None:
		raise CheckinDueError('missing record_id in backend payload')

	return StoredAccountRecord(
		record_id=str(record_id),
		provider=str(data.get('provider', CHECKIN_DUE_PROVIDER)),
		name=str(data.get('name', '')),
		username=str(data.get('username', '')),
		password=str(data.get('password', '')),
		registered_at=data.get('registered_at'),
		checkin_date=data.get('checkin_date'),
		balance_before=data.get('balance_before'),
		balance_after=data.get('balance_after'),
		balance_delta=data.get('balance_delta'),
		used_quota_before=data.get('used_quota_before'),
		used_quota_after=data.get('used_quota_after'),
		checkin_reward_raw=data.get('checkin_reward_raw'),
		last_status=data.get('last_status'),
		raw_result_json=data.get('raw_result_json'),
	)


def _build_success_payload(update: CheckinSuccessUpdate) -> dict[str, object]:
	return {
		'checkin_date': update.checkin_date,
		'balance_before': update.balance_before,
		'balance_after': update.balance_after,
		'balance_delta': update.balance_delta,
		'used_quota_before': update.used_quota_before,
		'used_quota_after': update.used_quota_after,
		'checkin_reward_raw': update.checkin_reward_raw,
		'last_status': update.last_status,
		'raw_result_json': update.raw_result_json,
	}


class SqliteCheckinDueRepository:
	def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
		self.db_path = Path(db_path)
		if not self.db_path.exists():
			raise FileNotFoundError(self.db_path)
		self.conn = connect_db(self.db_path)
		ensure_schema(self.conn)

	def list_accounts(self, provider_scope: str) -> list[StoredAccountRecord]:
		cursor = self.conn.execute(
			'''
			SELECT
				id,
				name,
				provider,
				username,
				password,
				registered_at,
				checkin_date,
				balance_before,
				balance_after,
				balance_delta,
				used_quota_before,
				used_quota_after,
				checkin_reward_raw,
				last_status,
				raw_result_json
			FROM registered_accounts
			WHERE provider = ?
			ORDER BY id ASC
			''',
			(provider_scope,),
		)
		return [_record_from_row(row) for row in cursor.fetchall()]

	def save_checkin_success(self, record_id: str, update: CheckinSuccessUpdate) -> None:
		try:
			numeric_id = int(record_id)
		except ValueError as exc:
			raise CheckinDueError(f'invalid sqlite record_id: {record_id}') from exc

		payload = _build_success_payload(update)
		fields = ', '.join(f'{key} = ?' for key in payload)
		values = list(payload.values()) + [numeric_id]
		self.conn.execute(f'UPDATE registered_accounts SET {fields} WHERE id = ?', values)
		self.conn.commit()

	def close(self) -> None:
		self.conn.close()

	def __enter__(self) -> 'SqliteCheckinDueRepository':
		return self

	def __exit__(self, exc_type, exc, tb) -> None:
		self.close()


class WorkerCheckinDueRepository:
	def __init__(self, worker_url: str, worker_token: str, client: httpx.Client | None = None):
		url = worker_url.strip()
		token = worker_token.strip()
		if not url:
			raise CheckinDueConfigurationError('worker_url is required')
		if not token:
			raise CheckinDueConfigurationError('worker_token is required')

		self.worker_url = url.rstrip('/')
		self.worker_token = token
		self.client = client or httpx.Client(timeout=30.0)
		self._owns_client = client is None

	def _headers(self) -> dict[str, str]:
		return {'Authorization': f'Bearer {self.worker_token}'}

	def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
		url = f'{self.worker_url}{path}'
		try:
			response = self.client.request(method, url, headers=self._headers(), timeout=30.0, **kwargs)
		except httpx.HTTPError as exc:
			raise CheckinDueUnavailableError(f'worker request failed: {exc}') from exc
		return response

	def _raise_for_status(self, response: httpx.Response) -> None:
		if response.status_code in {401, 403}:
			raise CheckinDueAuthError(f'worker auth failed: HTTP {response.status_code}')
		if response.status_code >= 400:
			raise CheckinDueUnavailableError(f'worker backend unavailable: HTTP {response.status_code}')

	def _parse_accounts(self, response: httpx.Response) -> list[StoredAccountRecord]:
		self._raise_for_status(response)
		try:
			payload = response.json()
		except Exception as exc:
			raise CheckinDueError(f'worker returned invalid JSON: {exc}') from exc

		if isinstance(payload, list):
			raw_records = payload
		elif isinstance(payload, dict):
			raw_records = payload.get('records') or payload.get('data') or payload.get('items') or []
		else:
			raise CheckinDueError('worker returned unsupported payload type')

		records: list[StoredAccountRecord] = []
		for item in raw_records:
			if not isinstance(item, dict):
				raise CheckinDueError('worker returned non-object account record')
			records.append(_record_from_mapping(item))
		return records

	def list_accounts(self, provider_scope: str) -> list[StoredAccountRecord]:
		response = self._request('GET', WORKER_ACCOUNTS_PATH, params={'provider': provider_scope})
		return self._parse_accounts(response)

	def save_checkin_success(self, record_id: str, update: CheckinSuccessUpdate) -> None:
		response = self._request(
			'POST',
			f'{WORKER_ACCOUNTS_PATH}/{record_id}/success',
			json=_build_success_payload(update),
		)
		self._raise_for_status(response)

	def close(self) -> None:
		if self._owns_client:
			self.client.close()

	def __enter__(self) -> 'WorkerCheckinDueRepository':
		return self

	def __exit__(self, exc_type, exc, tb) -> None:
		self.close()


def build_backend_repository(
	backend: str,
	*,
	db_path: Path | str = DEFAULT_DB_PATH,
	worker_url: str | None = None,
	worker_token: str | None = None,
	client: httpx.Client | None = None,
) -> CheckinDueRepository:
	name = backend.strip().lower()
	if name == 'sqlite':
		return SqliteCheckinDueRepository(db_path)
	if name == 'worker':
		if not worker_url or not worker_token:
			raise CheckinDueConfigurationError('worker_url and worker_token are required for worker backend')
		return WorkerCheckinDueRepository(worker_url, worker_token, client=client)
	raise CheckinDueConfigurationError(f'unsupported backend: {backend}')
