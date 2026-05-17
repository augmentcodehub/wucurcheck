#!/usr/bin/env python3
"""
One-command local pipeline:
1. Generate a safe test account file
2. Register + check in + persist to SQLite
3. Export GitHub Secrets JSON and CSV
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
	from utils.logger import get_logger
except ImportError:
	import logging; get_logger = lambda n: logging.getLogger(n)

log = get_logger('tools.run_wucur_pipeline')

TOOLS_DIR = Path(__file__).resolve().parents[1]
MAKE_SCRIPT = TOOLS_DIR / 'account_generation' / 'make_wucur_test_account.py'
REGISTER_DB_SCRIPT = TOOLS_DIR / 'register' / 'register_one_account_to_db.py'
EXPORT_SCRIPT = TOOLS_DIR / 'export' / 'export_wucur_accounts.py'


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


def run_step(name: str, command: list[str]) -> int:
	log.info('{name}')
	log.info('{" ".join(command)}')
	result = subprocess.run(command, check=False)
	if result.returncode == 0:
		log.info('{name}')
	else:
		log.error('{name} exit_code={result.returncode}')
	return result.returncode


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Run the local Wucur pipeline in one command.')
	parser.add_argument('--sequence', type=int, required=True, help='Sequence number for test account generation')
	parser.add_argument('--output', default='artifacts/one-account-checkin-next.json', help='Generated test account JSON file')
	parser.add_argument('--domain', default='e.com', help='Email domain for generated test account')
	parser.add_argument('--password', default='123Claude&Codex', help='Password for generated test account')
	parser.add_argument('--db', default='artifacts/wucur_accounts.sqlite3', help='SQLite database file')
	parser.add_argument('--json-output', default='artifacts/github-secrets-accounts.json', help='GitHub Secrets JSON output file')
	parser.add_argument('--csv-output', default='artifacts/accounts.csv', help='CSV backup output file')
	args = parser.parse_args(argv)

	python_exe = sys.executable

	generate_cmd = [
		python_exe,
		str(MAKE_SCRIPT),
		'--sequence',
		str(args.sequence),
		'--output',
		args.output,
		'--domain',
		args.domain,
		'--password',
		args.password,
	]
	register_cmd = [
		python_exe,
		str(REGISTER_DB_SCRIPT),
		'--file',
		args.output,
		'--db',
		args.db,
	]
	export_cmd = [
		python_exe,
		str(EXPORT_SCRIPT),
		'--db',
		args.db,
		'--json-output',
		args.json_output,
		'--csv-output',
		args.csv_output,
	]

	for step_name, command in [
		('generate_test_account', generate_cmd),
		('register_and_persist', register_cmd),
		('export_outputs', export_cmd),
	]:
		exit_code = run_step(step_name, command)
		if exit_code != 0:
			return exit_code

	log.info('Pipeline completed successfully')
	log.info('test_account_file: {args.output}')
	log.info('sqlite_db: {args.db}')
	log.info('github_json: {args.json_output}')
	log.info('csv_backup: {args.csv_output}')
	log.info('next_query_command: uv run wucur query --limit 3')
	return 0


if __name__ == '__main__':
	sys.exit(main())
