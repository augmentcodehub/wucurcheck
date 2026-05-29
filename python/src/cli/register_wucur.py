#!/usr/bin/env python3
# DEPRECATED: Use cli/register.py --provider wucur
"""Wucur account registration helper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from adapters.http import wucur_client
from core.application.register_and_checkin_account_use_case import RegisterAndCheckinAccountUseCase
from core.provider_profile import ProviderProfileResolver
from utils.config import AccountConfig, ProviderConfig


DEFAULT_OUTPUT_PATH = Path('artifacts/accounts.json')


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


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


def _load_provider(name: str = 'wucur') -> ProviderConfig:
	profile = ProviderProfileResolver().resolve(name)
	return ProviderConfig.from_profile(profile)


def _build_result_payload(result, account_name: str) -> dict[str, object]:
	payload = {
		'username': account_name,
		'register': result.register,
		'login': result.login,
		'checkin': result.checkin,
		'user_info': result.user_info,
	}
	if result.user_info_after_checkin is not None:
		payload['user_info_after_checkin'] = result.user_info_after_checkin
	return payload


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

	client = WucurCheckinClient()
	output_path = Path(args.output)
	output_path.parent.mkdir(parents=True, exist_ok=True)

	try:
		provider = _load_provider('wucur')
		account = AccountConfig(provider='wucur', name=args.name, username=args.username, password=args.password)
		use_case = RegisterAndCheckinAccountUseCase(client)
		result = use_case.run(account, provider, skip_checkin=args.skip_checkin, skip_balance=args.skip_balance)

		if args.json:
			print(json.dumps(_build_result_payload(result, args.username), ensure_ascii=False))
			return 0 if result.success else 1

		if not result.success:
			failure = result.message or 'Register failed'
			if isinstance(result.register, dict) and not result.register.get('success'):
				failure = str(result.register.get('message') or failure)
			elif isinstance(result.login, dict) and not result.login.get('success'):
				failure = str(result.login.get('message') or failure)
			print(f'[FAILED] {failure}')
			return 1

		print('[SUCCESS] Register succeeded')
		print('[SUCCESS] Login succeeded')
		print(f'[INFO] Account saved to {output_path}')

		balance_before = wucur_client.extract_balance_summary(result.user_info)
		balance_after = wucur_client.extract_balance_summary(result.user_info_after_checkin)
		if balance_before:
			print(f'[INFO] Balance before check-in: ${balance_before["quota"]}, Used: ${balance_before["used_quota"]}')
		elif result.user_info:
			print(f'[WARN] Failed to get user info: {result.user_info}')

		if isinstance(result.checkin, dict):
			if result.checkin.get('success'):
				print(f'[SUCCESS] Check-in result: {result.checkin}')
				if balance_after:
					print(
						f'[INFO] Balance after check-in: ${balance_after["quota"]}, Used: {balance_after["used_quota"]}'
					)
				if balance_before and balance_after:
					change = round(balance_after['quota'] - balance_before['quota'], 2)
					print(f'[INFO] Balance delta: ${change}')
			else:
				print(f'[INFO] Check-in response: {result.checkin}')
		return 0
	finally:
		client.close()


if __name__ == '__main__':
	sys.exit(main())
