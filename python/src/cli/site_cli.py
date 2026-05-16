#!/usr/bin/env python3
"""Canonical CLI for AnyRouter / Wucur site commands."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from core.application.check_due_accounts_use_case import CheckDueAccountsUseCase
from core.application.list_accounts_use_case import ListAccountsUseCase
from core.application.register_and_checkin_account_use_case import RegisterAndCheckinAccountUseCase
from core.application.request_normalizer import normalize_command_request
from core.provider_profile import ProviderProfileResolver
from adapters.checkin.checkin_due_service import CheckinDueService
from adapters.http import wucur_client
from adapters.persistence.sqlite.account_registry_db import DEFAULT_DB_PATH
from adapters.persistence.sqlite.checkin_due_repository import build_backend_repository
import scripts.query_wucur_accounts_db as query_wucur_accounts_db
from utils.logger import get_logger
from utils.config import AccountConfig, ProviderConfig


LOGGER = get_logger('cli.site_cli')


class WucurCheckinClient:
	def __init__(self):
		self._client = httpx.Client(http2=True, timeout=30.0)

	def register_account(self, username: str, password: str) -> dict:
		return wucur_client.register_account(self._client, username, password)

	def login_account(self, username: str, password: str) -> dict:
		return wucur_client.login_account(self._client, username, password)

	def checkin_account(self, headers: dict, sign_in_url: str) -> dict:
		return wucur_client.checkin_account(self._client, headers, sign_in_url)

	def get_user_info(self, headers: dict, user_info_url: str) -> dict:
		return wucur_client.get_user_info(self._client, headers, user_info_url)

	def login_with_session(self, account_name: str, provider_config: ProviderConfig, account: AccountConfig) -> str | None:
		login_data = self.login_account(account.username or '', account.password or '')
		if not login_data.get('success'):
			return None
		return wucur_client.extract_login_user_id_from_payload(login_data)

	def close(self) -> None:
		self._client.close()

	def __enter__(self) -> 'WucurCheckinClient':
		return self

	def __exit__(self, exc_type, exc, tb) -> None:
		self.close()


def _build_request(args: argparse.Namespace) -> dict[str, object]:
	return {
		'command': args.command,
		'provider': args.provider,
		'backend': args.backend,
		'scope': args.scope,
		'account': {'name': args.name, 'username': args.username, 'password': args.password},
	}


def _load_provider_config(provider_name: str) -> ProviderConfig:
	try:
		profile = ProviderProfileResolver().resolve(provider_name)
	except KeyError as exc:
		message = exc.args[0] if exc.args else str(exc)
		raise ValueError(message) from exc
	return ProviderConfig.from_profile(profile)


def _build_register_json_payload(request, result) -> dict[str, object]:
	account = request.account or {}
	payload = {
		'username': account.get('username'),
		'register': result.register,
		'login': result.login,
		'checkin': result.checkin,
		'user_info': result.user_info,
	}
	if result.user_info_after_checkin is not None:
		payload['user_info_after_checkin'] = result.user_info_after_checkin
	return payload


def _print_register_result(request, result) -> int:
	if not result.success:
		failure = result.message or 'register failed'
		for candidate in (result.register, result.login, result.checkin):
			if isinstance(candidate, dict) and candidate.get('success') is False:
				failure = str(candidate.get('message') or failure)
				break
		print(f'[FAILED] {failure}')
		return 1

	print('[SUCCESS] Register succeeded')
	print('[SUCCESS] Login succeeded')

	balance_before = wucur_client.extract_balance_summary(result.user_info)
	balance_after = wucur_client.extract_balance_summary(result.user_info_after_checkin)
	if balance_before:
		print(
			f'[INFO] Balance before check-in: ${balance_before["quota"]}, '
			f'Used: ${balance_before["used_quota"]}'
		)
	elif result.user_info:
		print(f'[WARN] Failed to get user info: {result.user_info}')

	if isinstance(result.checkin, dict):
		if result.checkin.get('success'):
			print(f'[SUCCESS] Check-in result: {result.checkin}')
			if balance_after:
				print(
					f'[INFO] Balance after check-in: ${balance_after["quota"]}, '
					f'Used: ${balance_after["used_quota"]}'
				)
			if balance_before and balance_after:
				change = round(balance_after['quota'] - balance_before['quota'], 2)
				print(f'[INFO] Balance delta: ${change}')
		else:
			print(f'[INFO] Check-in response: {result.checkin}')

	return 0


def _run_register_command(request, args) -> int:
	provider_config = _load_provider_config(request.provider)
	if provider_config.name != 'wucur':
		raise ValueError(f'UNSUPPORTED_PROVIDER: {provider_config.name}')

	account_data = request.account or {}
	account = AccountConfig(
		provider=request.provider,
		name=account_data['name'],
		username=account_data['username'],
		password=account_data['password'],
	)

	if not args.json:
		LOGGER.info(
			'Registering single account',
			extra={
				'account_name': account.name,
				'provider': account.provider,
				'username': account.username,
				'skip_checkin': str(args.skip_checkin).lower(),
			},
		)

	with WucurCheckinClient() as client:
		use_case = RegisterAndCheckinAccountUseCase(client)
		result = use_case.run(
			account,
			provider_config,
			skip_checkin=args.skip_checkin,
			skip_balance=args.skip_balance,
		)

	if args.json:
		print(json.dumps(_build_register_json_payload(request, result), ensure_ascii=False))
		return 0 if result.success else 1

	return _print_register_result(request, result)


def _run_list_command(request, args) -> int:
	_load_provider_config(request.provider)
	repository = build_backend_repository(
		args.backend,
		db_path=args.db,
		worker_url=args.worker_url,
		worker_token=args.worker_token,
	)

	with repository:
		use_case = ListAccountsUseCase(repository)
		result = use_case.run(provider_scope=request.provider)

	records = list(result.records)
	if args.backend == 'sqlite':
		records.reverse()

	limit = max(int(args.limit), 0)
	if limit:
		records = records[:limit]
	else:
		records = []

	if not records:
		LOGGER.info('No account records found')
		return 0

	source = str(args.db) if args.backend == 'sqlite' else 'worker backend'
	LOGGER.info('Loaded records', extra={'count': len(records), 'source': source})

	query_wucur_accounts_db.print_table([asdict(record) for record in records])
	return 0


def _run_checkin_command(request, args) -> int:
	provider_config = _load_provider_config(request.provider)
	if provider_config.name != 'wucur':
		raise ValueError(f'UNSUPPORTED_PROVIDER: {provider_config.name}')
	repository = build_backend_repository(
		args.backend,
		db_path=args.db,
		worker_url=args.worker_url,
		worker_token=args.worker_token,
	)

	with repository:
		service = CheckinDueService(repository, provider_config)
		use_case = CheckDueAccountsUseCase(service)
		summary = use_case.run(
			as_of=args.as_of,
			timezone=args.timezone,
			dry_run=args.dry_run,
			provider_scope=request.provider,
		)

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
	return summary.exit_code


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Canonical CLI for AnyRouter / Wucur site commands.')
	parser.add_argument('command', choices=['register', 'list', 'checkin'])
	parser.add_argument('--provider', default='wucur')
	parser.add_argument('--backend', default='sqlite')
	parser.add_argument('--scope', default='due')
	parser.add_argument('--db', default=str(DEFAULT_DB_PATH))
	parser.add_argument('--limit', type=int, default=20)
	parser.add_argument('--worker-url')
	parser.add_argument('--worker-token')
	parser.add_argument('--as-of')
	parser.add_argument('--timezone', default='Asia/Shanghai')
	parser.add_argument('--dry-run', action='store_true')
	parser.add_argument('--name')
	parser.add_argument('--username')
	parser.add_argument('--password')
	parser.add_argument('--skip-checkin', action='store_true')
	parser.add_argument('--skip-balance', action='store_true')
	parser.add_argument('--json', action='store_true')
	try:
		args = parser.parse_args(argv)
	except SystemExit as exc:
		return int(exc.code or 0)

	try:
		normalized = normalize_command_request(_build_request(args))
		if normalized.command == 'register':
			return _run_register_command(normalized, args)
		if normalized.command == 'list':
			return _run_list_command(normalized, args)
		return _run_checkin_command(normalized, args)
	except Exception as exc:
		LOGGER.error(str(exc))
		return 1


if __name__ == '__main__':
	sys.exit(main())
