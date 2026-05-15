#!/usr/bin/env python3
"""
Wucur account registration helper.

Flow:
1. Register with username/password
2. Login to obtain session cookie
3. Optionally check in
4. Optionally fetch balance information
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import httpx

DEFAULT_OUTPUT_PATH = Path('accounts.json')
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

try:
	from .wucur_client import (
		BASE_URL,
		CHECKIN_PATH,
		USER_INFO_PATH,
		build_headers,
		checkin_account,
		extract_balance_summary,
		extract_login_user_id_from_payload,
		get_user_info,
		login_account,
		register_account,
	)
except ImportError:  # pragma: no cover - direct script execution fallback
	from wucur_client import (
		BASE_URL,
		CHECKIN_PATH,
		USER_INFO_PATH,
		build_headers,
		checkin_account,
		extract_balance_summary,
		extract_login_user_id_from_payload,
		get_user_info,
		login_account,
		register_account,
	)


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


def load_accounts_file(path: Path) -> list[dict]:
	if not path.exists():
		return []
	try:
		data = json.loads(path.read_text(encoding='utf-8'))
	except json.JSONDecodeError as exc:
		raise ValueError(f'Invalid JSON in {path}: {exc}') from exc
	if not isinstance(data, list):
		raise ValueError(f'{path} must contain a JSON array')
	return data


def save_accounts_file(path: Path, accounts: list[dict]) -> None:
	path.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding='utf-8')


def append_account_record(path: Path, username: str, password: str, name: str | None = None) -> None:
	accounts = load_accounts_file(path)
	account_name = name or username
	new_record = {
		'name': account_name,
		'provider': 'wucur',
		'username': username,
		'password': password,
	}
	for record in accounts:
		if isinstance(record, dict) and record.get('provider') == 'wucur' and record.get('username') == username:
			record.update(new_record)
			save_accounts_file(path, accounts)
			return
	accounts.append(new_record)
	save_accounts_file(path, accounts)


def build_authenticated_headers(user_id: str) -> dict[str, str]:
	headers = build_headers('/')
	headers['new-api-user'] = user_id
	return headers


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Register and optionally check in a Wucur account.')
	parser.add_argument('--username', required=True, help='Wucur username/email')
	parser.add_argument('--password', required=True, help='Wucur password')
	parser.add_argument('--skip-checkin', action='store_true', help='Skip the check-in step after login')
	parser.add_argument('--skip-balance', action='store_true', help='Skip fetching balance after login')
	parser.add_argument('--json', action='store_true', help='Print machine-readable JSON output')
	parser.add_argument('--name', help='Optional account display name to store in accounts.json')
	parser.add_argument(
		'--output',
		default=str(DEFAULT_OUTPUT_PATH),
		help='Path to the local JSON file that stores ANYROUTER_ACCOUNTS-compatible records',
	)
	args = parser.parse_args(argv)

	client = httpx.Client(http2=True, timeout=30.0)
	output_path = Path(args.output)
	result: dict[str, object] = {
		'username': args.username,
		'register': None,
		'login': None,
		'checkin': None,
		'user_info': None,
	}

	try:
		register_data = register_account(client, args.username, args.password)
		result['register'] = register_data

		if not register_data.get('success'):
			if args.json:
				print(json.dumps(result, ensure_ascii=False))
			else:
				print(f'[FAILED] Register failed: {register_data.get("message", "Unknown error")}')
			return 1

		login_data = login_account(client, args.username, args.password)
		result['login'] = login_data
		if not login_data.get('success'):
			if args.json:
				print(json.dumps(result, ensure_ascii=False))
			else:
				print(f'[FAILED] Login failed: {login_data.get("message", "Unknown error")}')
			return 1

		append_account_record(output_path, args.username, args.password, args.name)

		user_id = extract_login_user_id_from_payload(login_data) or ''
		user_headers = build_authenticated_headers(user_id) if user_id else None
		if user_headers and not args.skip_balance:
			result['user_info'] = get_user_info(client, user_headers, f'{BASE_URL}{USER_INFO_PATH}')
		elif not user_id and not args.skip_balance:
			result['user_info'] = {'success': False, 'message': 'Login succeeded but user id was not found'}
		balance_before = extract_balance_summary(result['user_info'])

		if not args.skip_checkin:
			if user_headers is None:
				result['checkin'] = {'success': False, 'message': 'Login succeeded but user id was not found'}
			else:
				result['checkin'] = checkin_account(client, user_headers, f'{BASE_URL}{CHECKIN_PATH}')
				if not args.skip_balance:
					result['user_info_after_checkin'] = get_user_info(
						client,
						user_headers,
						f'{BASE_URL}{USER_INFO_PATH}',
					)
		balance_after = extract_balance_summary(result.get('user_info_after_checkin')) or balance_before

		if args.json:
			print(json.dumps(result, ensure_ascii=False))
			return 0

		print('[SUCCESS] Register succeeded')
		print('[SUCCESS] Login succeeded')
		print(f'[INFO] Account saved to {output_path}')
		if balance_before:
			print(f'[INFO] Balance before check-in: ${balance_before["quota"]}, Used: ${balance_before["used_quota"]}')
		elif result['user_info']:
			print(f'[WARN] Failed to get user info: {result["user_info"]}')
		if result['checkin']:
			checkin = result['checkin']
			if isinstance(checkin, dict):
				if checkin.get('success'):
					print(f'[SUCCESS] Check-in result: {checkin}')
					if balance_after:
						print(
							f'[INFO] Balance after check-in: ${balance_after["quota"]}, Used: ${balance_after["used_quota"]}'
						)
					if balance_before and balance_after:
						change = round(balance_after['quota'] - balance_before['quota'], 2)
						print(f'[INFO] Balance delta: ${change}')
				else:
					print(f'[INFO] Check-in response: {checkin}')
		return 0
	finally:
		client.close()


if __name__ == '__main__':
	sys.exit(main())
