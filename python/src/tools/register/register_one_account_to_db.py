#!/usr/bin/env python3
"""
Register one Wucur account and write the successful result to SQLite.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from adapters.persistence.sqlite.account_registry_db import DEFAULT_DB_PATH, connect_db, ensure_schema, upsert_registered_account
from tools.register.register_one_account import load_account_from_file, load_account_from_json_text, validate_account
from utils.logger import get_logger

REGISTER_SCRIPT_PATH = Path(__file__).resolve().parents[2] / 'cli' / 'register_wucur.py'


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


LOGGER = get_logger('tools.register.register_one_account_to_db')


def extract_balance(user_info: dict | None) -> tuple[float | None, float | None]:
	if not isinstance(user_info, dict) or not user_info.get('success'):
		return None, None
	if 'quota' in user_info and 'used_quota' in user_info:
		return round(float(user_info.get('quota', 0)), 2), round(float(user_info.get('used_quota', 0)), 2)
	data = user_info.get('data', {})
	quota = round(data.get('quota', 0) / 500000, 2)
	used_quota = round(data.get('used_quota', 0) / 500000, 2)
	return quota, used_quota


def run_register_json(account: dict[str, str], skip_checkin: bool) -> tuple[int, dict | None]:
	command = [
		sys.executable,
		str(REGISTER_SCRIPT_PATH),
		'--name',
		account['name'],
		'--username',
		account['username'],
		'--password',
		account['password'],
		'--json',
	]
	if skip_checkin:
		command.append('--skip-checkin')

	LOGGER.info(
		'Registering single account and writing result to SQLite',
		extra={
			'account_name': account['name'],
			'provider': account['provider'],
			'username': account['username'],
			'skip_checkin': str(skip_checkin).lower(),
		},
	)

	result = subprocess.run(command, check=False, capture_output=True, text=True, encoding='utf-8', errors='replace')
	stdout_text = result.stdout.strip()
	if stdout_text:
		print(stdout_text)
	if result.stderr.strip():
		print(result.stderr.strip(), file=sys.stderr)

	if result.returncode != 0:
		return result.returncode, None

	try:
		payload = json.loads(stdout_text)
	except json.JSONDecodeError as exc:
		log.error('Could not parse JSON result from cli/register_wucur.py: {exc}')
		return 1, None

	return result.returncode, payload


def persist_success(account: dict[str, str], payload: dict, db_path: Path) -> None:
	register_data = payload.get('register') or {}
	login_data = payload.get('login') or {}
	checkin_data = payload.get('checkin') or {}
	user_info_before = payload.get('user_info')
	user_info_after = payload.get('user_info_after_checkin') or payload.get('user_info')

	balance_before, used_before = extract_balance(user_info_before)
	balance_after, used_after = extract_balance(user_info_after)
	balance_delta = None
	if balance_before is not None and balance_after is not None:
		balance_delta = round(balance_after - balance_before, 2)

	checkin_reward_raw = None
	checkin_date = None
	if isinstance(checkin_data, dict):
		data_node = checkin_data.get('data')
		if isinstance(data_node, dict):
			checkin_reward_raw = data_node.get('quota_awarded')
			checkin_date = data_node.get('checkin_date')

	last_status = 'registered'
	if login_data.get('success'):
		last_status = 'logged_in'
	if checkin_data:
		last_status = 'checkin_success' if checkin_data.get('success') else 'checkin_response'

	raw_result_json = json.dumps(payload, ensure_ascii=False)

	conn = connect_db(db_path)
	try:
		ensure_schema(conn)
		upsert_registered_account(
			conn,
			name=account['name'],
			provider=account['provider'],
			username=account['username'],
			password=account['password'],
			registered_at=datetime.now().isoformat(timespec='seconds'),
			checkin_date=checkin_date,
			balance_before=balance_before,
			balance_after=balance_after,
			balance_delta=balance_delta,
			used_quota_before=used_before,
			used_quota_after=used_after,
			checkin_reward_raw=checkin_reward_raw,
			last_status=last_status,
			raw_result_json=raw_result_json,
		)
	finally:
		conn.close()

	LOGGER.info('SQLite record saved to %s', db_path)


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Register one Wucur account and persist the successful result to SQLite.')
	parser.add_argument('--json-input', help='Single JSON object string')
	parser.add_argument('--file', help='Path to a JSON file containing one account object')
	parser.add_argument('--stdin', action='store_true', help='Read a single JSON object from standard input')
	parser.add_argument('--skip-checkin', action='store_true', help='Skip the check-in step')
	parser.add_argument('--db', default=str(DEFAULT_DB_PATH), help='SQLite database file path')
	args = parser.parse_args(argv)

	input_sources = sum(1 for item in [args.json_input, args.file, args.stdin] if item)
	if input_sources != 1:
		LOGGER.error('Provide exactly one of --json-input, --file, or --stdin')
		return 1

	try:
		if args.file:
			account = load_account_from_file(Path(args.file))
		elif args.stdin:
			account = load_account_from_json_text(sys.stdin.read())
		else:
			account = load_account_from_json_text(args.json_input)
		validated = validate_account(account)
	except Exception as exc:
		log.error('{exc}')
		return 1

	exit_code, payload = run_register_json(validated, skip_checkin=args.skip_checkin)
	if exit_code != 0 or payload is None:
		LOGGER.error('Registration flow failed', extra={'exit_code': exit_code})
		return exit_code or 1

	try:
		persist_success(validated, payload, Path(args.db))
	except Exception as exc:
		LOGGER.error(f'Registration succeeded but SQLite persistence failed: {exc}')
		return 1

	return 0


if __name__ == '__main__':
	sys.exit(main())
