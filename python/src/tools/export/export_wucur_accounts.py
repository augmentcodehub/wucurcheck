#!/usr/bin/env python3
"""
Export registered Wucur accounts from SQLite to:
1. GitHub Secrets-compatible JSON
2. CSV backup
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

try:
	from utils.logger import get_logger
except ImportError:
	import logging; get_logger = lambda n: logging.getLogger(n)

log = get_logger('tools.export_wucur_accounts')

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from adapters.persistence.sqlite.account_registry_db import DEFAULT_DB_PATH, connect_db, ensure_schema

DEFAULT_JSON_OUTPUT = Path('artifacts/github-secrets-accounts.json')
DEFAULT_CSV_OUTPUT = Path('artifacts/accounts.csv')


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


def fetch_rows(conn: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
	query = '''
		SELECT
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
			last_status
		FROM registered_accounts
		ORDER BY id DESC
	'''
	params: tuple = ()
	if limit is not None and limit > 0:
		query += ' LIMIT ?'
		params = (limit,)

	cursor = conn.execute(query, params)
	return cursor.fetchall()


def to_github_secret_format(rows: list[sqlite3.Row]) -> list[dict]:
	return [
		{
			'name': row['name'],
			'provider': row['provider'],
			'username': row['username'],
			'password': row['password'],
		}
		for row in rows
	]


def write_json_output(path: Path, payload: list[dict]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def write_csv_output(path: Path, rows: list[sqlite3.Row]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	fieldnames = [
		'name',
		'provider',
		'username',
		'password',
		'registered_at',
		'checkin_date',
		'balance_before',
		'balance_after',
		'balance_delta',
		'used_quota_before',
		'used_quota_after',
		'checkin_reward_raw',
		'last_status',
	]
	with path.open('w', encoding='utf-8-sig', newline='') as file:
		writer = csv.DictWriter(file, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			writer.writerow({field: row[field] for field in fieldnames})


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Export Wucur account records to GitHub Secrets JSON and CSV.')
	parser.add_argument('--db', default=str(DEFAULT_DB_PATH), help='SQLite database file path')
	parser.add_argument('--json-output', default=str(DEFAULT_JSON_OUTPUT), help='GitHub Secrets JSON output path')
	parser.add_argument('--csv-output', default=str(DEFAULT_CSV_OUTPUT), help='CSV output path')
	parser.add_argument('--limit', type=int, default=0, help='Optional number of latest rows to export, 0 means all')
	parser.add_argument('--stdout-json', action='store_true', help='Print GitHub Secrets JSON to stdout')
	args = parser.parse_args(argv)

	db_path = Path(args.db)
	if not db_path.exists():
		log.error('Database file not found: {db_path}')
		return 1

	conn = connect_db(db_path)
	try:
		ensure_schema(conn)
		rows = fetch_rows(conn, args.limit if args.limit > 0 else None)
	finally:
		conn.close()

	if not rows:
		log.info('No account records found')
		return 0

	json_payload = to_github_secret_format(rows)
	json_output_path = Path(args.json_output)
	csv_output_path = Path(args.csv_output)

	write_json_output(json_output_path, json_payload)
	write_csv_output(csv_output_path, rows)

	log.info('Exported {len(rows)} record(s)')
	log.info('github_json: {json_output_path}')
	log.info('csv_backup: {csv_output_path}')

	if args.stdout_json:
		print(json.dumps(json_payload, ensure_ascii=False, indent=2))

	return 0


if __name__ == '__main__':
	sys.exit(main())
