#!/usr/bin/env python3
"""
Generate a single Wucur test account file with enforced username length limits.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_OUTPUT = Path('artifacts/one-account-checkin-next.json')
DEFAULT_PASSWORD = '123Claude&Codex'
DEFAULT_DOMAIN = 'e.com'
DEFAULT_MAX_USERNAME_LENGTH = 20


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


def build_safe_username(
	sequence: int,
	domain: str,
	max_username_length: int,
	local_prefix: str = 'u',
	time_format: str = '%m%d%H%M',
) -> str:
	if '@' in domain:
		domain = domain.split('@', 1)[1]

	time_part = datetime.now().strftime(time_format)
	base_local = f'{local_prefix}{sequence}{time_part}'
	max_local_length = max_username_length - len(domain) - 1
	if max_local_length <= 0:
		raise ValueError('max_username_length is too small for the selected domain')

	local = base_local[:max_local_length]
	if not local:
		raise ValueError('Failed to generate a valid local part')

	username = f'{local}@{domain}'
	if len(username) > max_username_length:
		raise ValueError('Generated username still exceeds max length')
	return username


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Generate one safe Wucur test account JSON file.')
	parser.add_argument('--sequence', type=int, default=1, help='Sequence number for display name and username seed')
	parser.add_argument('--name-prefix', default='账号', help='Display name prefix')
	parser.add_argument('--domain', default=DEFAULT_DOMAIN, help='Email domain without @, default e.com')
	parser.add_argument('--password', default=DEFAULT_PASSWORD, help='Password to write into the JSON file')
	parser.add_argument(
		'--max-username-length',
		type=int,
		default=DEFAULT_MAX_USERNAME_LENGTH,
		help='Maximum username length, default 20',
	)
	parser.add_argument('--output', default=str(DEFAULT_OUTPUT), help='Output JSON file path')
	args = parser.parse_args(argv)

	try:
		username = build_safe_username(
			sequence=args.sequence,
			domain=args.domain,
			max_username_length=args.max_username_length,
		)
	except Exception as exc:
		print(f'[FAILED] {exc}')
		return 1

	account = {
		'name': f'{args.name_prefix}{args.sequence}',
		'provider': 'wucur',
		'username': username,
		'password': args.password,
	}

	output_path = Path(args.output)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	output_path.write_text(json.dumps(account, ensure_ascii=False, indent=2), encoding='utf-8')

	print(f'[SUCCESS] Generated test account file: {output_path}')
	print(f'[INFO] name: {account["name"]}')
	print(f'[INFO] username: {account["username"]}')
	print(f'[INFO] username_length: {len(account["username"])}')
	print(f'[INFO] max_username_length: {args.max_username_length}')
	print(f'[INFO] next_command: uv run wucur register --file .\\{output_path.name}')
	return 0


if __name__ == '__main__':
	sys.exit(main())
