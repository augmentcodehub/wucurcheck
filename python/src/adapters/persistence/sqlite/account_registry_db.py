#!/usr/bin/env python3
"""
SQLite helpers for local account registration records.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path('artifacts/wucur_accounts.sqlite3')


def connect_db(path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
	db_path = Path(path)
	db_path.parent.mkdir(parents=True, exist_ok=True)
	conn = sqlite3.connect(str(db_path))
	conn.row_factory = sqlite3.Row
	return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
	conn.execute(
		'''
		CREATE TABLE IF NOT EXISTS registered_accounts (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL,
			provider TEXT NOT NULL,
			username TEXT NOT NULL UNIQUE,
			password TEXT NOT NULL,
			registered_at TEXT NOT NULL,
			checkin_date TEXT,
			balance_before REAL,
			balance_after REAL,
			balance_delta REAL,
			used_quota_before REAL,
			used_quota_after REAL,
			checkin_reward_raw INTEGER,
			last_status TEXT NOT NULL,
			raw_result_json TEXT NOT NULL
		)
		'''
	)
	conn.commit()


def upsert_registered_account(
	conn: sqlite3.Connection,
	*,
	name: str,
	provider: str,
	username: str,
	password: str,
	registered_at: str,
	checkin_date: str | None,
	balance_before: float | None,
	balance_after: float | None,
	balance_delta: float | None,
	used_quota_before: float | None,
	used_quota_after: float | None,
	checkin_reward_raw: int | None,
	last_status: str,
	raw_result_json: str,
) -> None:
	conn.execute(
		'''
		INSERT INTO registered_accounts (
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
		)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(username) DO UPDATE SET
			name = excluded.name,
			provider = excluded.provider,
			password = excluded.password,
			registered_at = excluded.registered_at,
			checkin_date = excluded.checkin_date,
			balance_before = excluded.balance_before,
			balance_after = excluded.balance_after,
			balance_delta = excluded.balance_delta,
			used_quota_before = excluded.used_quota_before,
			used_quota_after = excluded.used_quota_after,
			checkin_reward_raw = excluded.checkin_reward_raw,
			last_status = excluded.last_status,
			raw_result_json = excluded.raw_result_json
		''',
		(
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
			raw_result_json,
		),
	)
	conn.commit()
