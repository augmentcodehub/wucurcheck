#!/usr/bin/env python3
"""
Thin CLI for the checkin-due service.

The CLI only parses arguments, constructs the repository and service, and
delegates the workflow to CheckinDueService.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

try:
	from .checkin_due_repository import build_backend_repository
	from .checkin_due_service import CheckinDueService
except ImportError:  # pragma: no cover - direct script execution fallback
	from checkin_due_repository import build_backend_repository
	from checkin_due_service import CheckinDueService

from utils.config import AppConfig


def _load_wucur_provider():
	provider = AppConfig.load_from_env().get_provider('wucur')
	if provider is None:
		raise RuntimeError('missing wucur provider configuration')
	return provider


def _print_summary(summary) -> None:
	print(
		'[SUMMARY] '
		f'scanned={summary.scanned} due={summary.due} skipped={summary.skipped} '
		f'succeeded={summary.succeeded} failed={summary.failed}'
	)
	if summary.error_code:
		print(f'[SUMMARY] error_code={summary.error_code}')


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Run the Wucur checkin-due service.')
	parser.add_argument('--backend', choices=['sqlite', 'worker'], default='sqlite', help='Repository backend')
	parser.add_argument('--db', default='wucur_accounts.sqlite3', help='SQLite database path')
	parser.add_argument('--worker-url', help='Worker backend base URL')
	parser.add_argument('--worker-token', help='Worker backend bearer token')
	parser.add_argument('--as-of', help='Override the date used for due-account classification')
	parser.add_argument('--timezone', default='Asia/Shanghai', help='Timezone used when --as-of is not provided')
	parser.add_argument('--dry-run', action='store_true', help='Only classify accounts without writing results')
	parser.add_argument('--provider-scope', default='wucur', help='Provider scope to process')
	args = parser.parse_args(argv)

	try:
		provider_config = _load_wucur_provider()
		repository = build_backend_repository(
			args.backend,
			db_path=args.db,
			worker_url=args.worker_url,
			worker_token=args.worker_token,
		)
	except Exception as exc:
		print(f'[FAILED] {exc}')
		return 1

	with repository:
		service = CheckinDueService(repository, provider_config)
		summary = service.run(
			as_of=args.as_of,
			timezone=args.timezone,
			dry_run=args.dry_run,
			provider_scope=args.provider_scope,
		)

	_print_summary(summary)
	return summary.exit_code


if __name__ == '__main__':
	sys.exit(main())
