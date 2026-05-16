#!/usr/bin/env python3
"""
Thin wrapper:
- Generate one account from rule config
- Delegate the actual registration to register_wucur.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
	from .account_rule_engine import generate_accounts, load_rule_config, write_example_rule_config
except ImportError:  # pragma: no cover - direct script execution fallback
	from account_rule_engine import generate_accounts, load_rule_config, write_example_rule_config

DEFAULT_CONFIG_PATH = Path('artifacts/register_wucur_wrapper.json')
REGISTER_SCRIPT_PATH = Path(__file__).resolve().parents[2] / 'cli' / 'register_wucur.py'


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


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

	print('[INFO] Generated account:')
	print(f'  sequence: {account["sequence"]}')
	print(f'  seed: {account["seed"]}')
	print(f'  name: {account["name"]}')
	print(f'  username: {account["username"]}')
	print(f'  password: {account["password"]}')
	print('[INFO] Delegating to cli/register_wucur.py')

	result = subprocess.run(command, check=False)
	return result.returncode


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Generate one Wucur account from rule config and call register_wucur.py')
	parser.add_argument('--config', default=str(DEFAULT_CONFIG_PATH), help='Path to wrapper JSON config')
	parser.add_argument('--init-config', action='store_true', help='Create an example config file and exit')
	parser.add_argument('--index', type=int, default=0, help='Which generated account index to use, default 0')
	parser.add_argument('--skip-checkin', action='store_true', help='Override config and skip check-in')
	parser.add_argument('--json', action='store_true', help='Override config and print JSON result')
	args = parser.parse_args(argv)

	config_path = Path(args.config)
	if args.init_config:
		config_path.parent.mkdir(parents=True, exist_ok=True)
		write_example_rule_config(config_path)
		print(f'[SUCCESS] Example config written to {config_path}')
		return 0

	try:
		config = load_rule_config(config_path)
		accounts = generate_accounts(config)
	except Exception as exc:
		print(f'[FAILED] {exc}')
		return 1

	if not accounts:
		print('[FAILED] No accounts generated')
		return 1

	if args.index < 0 or args.index >= len(accounts):
		print(f'[FAILED] index out of range: {args.index}, generated count: {len(accounts)}')
		return 1

	skip_checkin = args.skip_checkin or config.skip_checkin
	json_output = args.json or config.json_output
	return run_register(accounts[args.index], skip_checkin=skip_checkin, json_output=json_output)


if __name__ == '__main__':
	sys.exit(main())
