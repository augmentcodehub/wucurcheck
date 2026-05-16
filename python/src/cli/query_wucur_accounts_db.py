#!/usr/bin/env python3
"""
Query local Wucur account records from SQLite.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import sqlite3
import sys
import unicodedata
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from adapters.persistence.sqlite.account_registry_db import DEFAULT_DB_PATH
from adapters.persistence.sqlite.checkin_due_repository import SqliteCheckinDueRepository
from core.application.list_accounts_use_case import ListAccountsUseCase
from utils.logger import get_logger


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


LOGGER = get_logger('cli.query_wucur_accounts_db')


def fetch_rows(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
	cursor = conn.execute(
		'''
		SELECT
			name,
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
		LIMIT ?
		''',
		(limit,),
	)
	return cursor.fetchall()


def format_value(value) -> str:
	if value is None:
		return '-'
	return str(value)


def display_width(text: str) -> int:
	width = 0
	for char in text:
		if unicodedata.east_asian_width(char) in {'W', 'F'}:
			width += 2
		else:
			width += 1
	return width


def pad_display(text: str, width: int) -> str:
	current = display_width(text)
	if current >= width:
		return text
	return text + (' ' * (width - current))


def print_table(rows: list[sqlite3.Row]) -> None:
	headers = [
		'名称',
		'用户名',
		'密码',
		'注册时间',
		'签到日期',
		'签到前余额',
		'签到后余额',
		'余额变化',
		'签到前已用',
		'签到后已用',
		'原始奖励',
		'状态',
	]
	data_rows = [
		[
			format_value(row['name']),
			format_value(row['username']),
			format_value(row['password']),
			format_value(row['registered_at']),
			format_value(row['checkin_date']),
			format_value(row['balance_before']),
			format_value(row['balance_after']),
			format_value(row['balance_delta']),
			format_value(row['used_quota_before']),
			format_value(row['used_quota_after']),
			format_value(row['checkin_reward_raw']),
			format_value(row['last_status']),
		]
		for row in rows
	]

	widths = [display_width(header) for header in headers]
	for data_row in data_rows:
		for idx, value in enumerate(data_row):
			widths[idx] = max(widths[idx], display_width(value))

	def border(left: str, middle: str, right: str, fill: str = '─') -> str:
		return left + middle.join(fill * width for width in widths) + right

	def build_line(values: list[str]) -> str:
		return '│' + '│'.join(f' {pad_display(value, widths[idx] - 2) if widths[idx] >= 2 else value} ' for idx, value in enumerate(values)) + '│'

	# Recalculate widths to include padding comfortably
	widths = [max(width, 4) + 2 for width in widths]

	print(border('┌', '┬', '┐'))
	print(build_line(headers))
	print(border('├', '┼', '┤'))
	for data_row in data_rows:
		print(build_line(data_row))
	print(border('└', '┴', '┘'))


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Query Wucur account records from local SQLite.')
	parser.add_argument('--db', default=str(DEFAULT_DB_PATH), help='SQLite database file path')
	parser.add_argument('--limit', type=int, default=20, help='Number of latest rows to show')
	args = parser.parse_args(argv)

	db_path = Path(args.db)
	if not db_path.exists():
		LOGGER.error('Database file not found', extra={'path': str(db_path)})
		return 1

	try:
		repository = SqliteCheckinDueRepository(db_path)
	except FileNotFoundError:
		print(f'[FAILED] Database file not found: {db_path}')
		return 1

	with repository:
		use_case = ListAccountsUseCase(repository)
		result = use_case.run(provider_scope='wucur')

	rows = [asdict(record) for record in result.records]
	rows.reverse()
	if args.limit > 0:
		rows = rows[: args.limit]
	else:
		rows = []

	if not rows:
		LOGGER.info('No account records found')
		return 0

	LOGGER.info('Loaded account records', extra={'count': len(rows), 'path': str(db_path)})
	print_table(rows)
	return 0


if __name__ == '__main__':
	sys.exit(main())
