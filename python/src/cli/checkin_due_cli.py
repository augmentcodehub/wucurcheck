#!/usr/bin/env python3
"""CLI entrypoint for due-account check-in."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from adapters.checkin.checkin_due_service import CheckinDueService
from adapters.persistence.sqlite.account_registry_db import DEFAULT_DB_PATH
from adapters.persistence.sqlite.checkin_due_repository import build_backend_repository
from core.application.check_due_accounts_use_case import CheckDueAccountsUseCase
from core.provider_profile import ProviderProfileResolver
from utils.logger import get_logger


LOGGER = get_logger('cli.checkin_due_cli')


def _load_wucur_provider():
	return ProviderProfileResolver().resolve('wucur')


def _print_summary(summary) -> None:
	LOGGER.info(
		'checkin summary',
		extra={
			'scanned': summary.scanned,
			'due': summary.due,
			'skipped': summary.skipped,
			'succeeded': summary.succeeded,
			'failed': summary.failed,
		},
	)
	if summary.error_code:
		LOGGER.info('checkin summary error', extra={'error_code': summary.error_code})


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Run the Wucur checkin-due service.')
	parser.add_argument('--backend', choices=['sqlite', 'worker'], default='sqlite', help='Repository backend')
	parser.add_argument('--db', default=str(DEFAULT_DB_PATH), help='SQLite database path')
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
		LOGGER.error(str(exc))
		return 1

	with repository:
		service = CheckinDueService(repository, provider_config)
		use_case = CheckDueAccountsUseCase(service)
		summary = use_case.run(
			as_of=args.as_of,
			timezone=args.timezone,
			dry_run=args.dry_run,
			provider_scope=args.provider_scope,
		)

	_print_summary(summary)
	return summary.exit_code


if __name__ == '__main__':
	sys.exit(main())
