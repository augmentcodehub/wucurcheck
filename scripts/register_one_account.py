#!/usr/bin/env python3
"""
Register one account from a JSON object.

This is intentionally single-account only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REGISTER_SCRIPT_PATH = Path(__file__).with_name('register_wucur.py')


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


def load_account_from_json_text(text: str) -> dict:
	try:
		data = json.loads(text)
	except json.JSONDecodeError as exc:
		raise ValueError(f'Invalid JSON input: {exc}') from exc
	if not isinstance(data, dict):
		raise ValueError('Input must be a single JSON object')
	return data


def load_account_from_file(path: Path) -> dict:
	if not path.exists():
		raise ValueError(f'File not found: {path}')
	return load_account_from_json_text(path.read_text(encoding='utf-8'))


def validate_account(account: dict) -> dict[str, str]:
	name = str(account.get('name', '')).strip()
	provider = str(account.get('provider', '')).strip()
	username = str(account.get('username', '')).strip()
	password = str(account.get('password', '')).strip()

	if not name:
		raise ValueError('Missing required field: name')
	if provider != 'wucur':
		raise ValueError(f'Unsupported provider: {provider!r}, expected "wucur"')
	if not username:
		raise ValueError('Missing required field: username')
	if not password:
		raise ValueError('Missing required field: password')

	return {
		'name': name,
		'provider': provider,
		'username': username,
		'password': password,
	}


def run_register(account: dict[str, str], skip_checkin: bool, json_output: bool) -> int:
	command = [
		sys.executable,
		str(REGISTER_SCRIPT_PATH),
		'--name',
		account['name'],
		'--username',
		account['username'],
		'--password',
		account['password'],
	]
	if skip_checkin:
		command.append('--skip-checkin')
	if json_output:
		command.append('--json')

	print('[INFO] Registering single account')
	print(f'  name: {account["name"]}')
	print(f'  provider: {account["provider"]}')
	print(f'  username: {account["username"]}')
	print(f'  skip_checkin: {str(skip_checkin).lower()}')
	print('[INFO] Calling scripts/register_wucur.py')

	result = subprocess.run(command, check=False)
	if result.returncode == 0:
		print('[SUCCESS] Account registration flow completed')
	else:
		print(f'[FAILED] Account registration flow failed with exit code {result.returncode}')
	return result.returncode


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Register one Wucur account from a JSON object or file.')
	parser.add_argument('--json-input', help='Single JSON object string')
	parser.add_argument('--file', help='Path to a JSON file containing one account object')
	parser.add_argument('--stdin', action='store_true', help='Read a single JSON object from standard input')
	parser.add_argument('--skip-checkin', action='store_true', help='Skip the check-in step')
	parser.add_argument('--json', action='store_true', help='Pass --json to the underlying registration script')
	args = parser.parse_args(argv)

	input_sources = sum(1 for item in [args.json_input, args.file, args.stdin] if item)
	if input_sources != 1:
		print('[FAILED] Provide exactly one of --json-input, --file, or --stdin')
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
		print(f'[FAILED] {exc}')
		return 1

	return run_register(validated, skip_checkin=args.skip_checkin, json_output=args.json)


if __name__ == '__main__':
	sys.exit(main())
