#!/usr/bin/env python3
"""
Batch check-in service for due Wucur accounts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from adapters.http.wucur_client import checkin_account, extract_balance_summary, get_user_info, login_with_session
from adapters.persistence.sqlite.checkin_due_repository import CheckinDueError
from core.domain import (
	CheckinDueSummary,
	CheckinSuccessUpdate,
	StoredAccountRecord,
	classify_due_accounts,
	resolve_as_of_date,
)
from core.ports.account_repository import AccountRepository as CheckinDueRepository
from utils.config import AccountConfig, ProviderConfig


WUCUR_PROVIDER = 'wucur'


@dataclass(frozen=True)
class CheckinAccountResult:
	success: bool
	error_code: str | None
	message: str | None = None


class CheckinDueService:
	def __init__(self, repository: CheckinDueRepository, provider_config: ProviderConfig):
		self.repository = repository
		self.provider_config = provider_config

	def _to_account_config(self, record: StoredAccountRecord) -> AccountConfig:
		return AccountConfig(
			provider=record.provider,
			name=record.name,
			username=record.username,
			password=record.password,
		)

	def run_account_checkin(
		self,
		record: StoredAccountRecord,
		*,
		checkin_date: date | None = None,
	) -> tuple[CheckinAccountResult, CheckinSuccessUpdate | None]:
		account = self._to_account_config(record)
		if record.provider != WUCUR_PROVIDER:
			return CheckinAccountResult(False, 'UNSUPPORTED_PROVIDER', f'unsupported provider: {record.provider}'), None

		import httpx

		client = httpx.Client(http2=True, timeout=30.0)
		try:
			login_user_id = login_with_session(client, record.name, self.provider_config, account)
			if not login_user_id:
				return CheckinAccountResult(False, 'CHECKIN_REQUEST_FAILED', 'login failed'), None

			headers = {
				'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
				'Accept': 'application/json, text/plain, */*',
				'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
				'Accept-Encoding': 'gzip, deflate, br, zstd',
				'Referer': self.provider_config.domain,
				'Origin': self.provider_config.domain,
				'Connection': 'keep-alive',
				'Sec-Fetch-Dest': 'empty',
				'Sec-Fetch-Mode': 'cors',
				'Sec-Fetch-Site': 'same-origin',
			}
			if self.provider_config.api_user_key and login_user_id:
				headers[self.provider_config.api_user_key] = login_user_id

			user_info_before = get_user_info(
				client, headers, f'{self.provider_config.domain}{self.provider_config.user_info_path}'
			)
			balance_before = extract_balance_summary(user_info_before)

			checkin_response = checkin_account(
				client, headers, f'{self.provider_config.domain}{self.provider_config.sign_in_path}'
			)
			if not checkin_response.get('success'):
				return CheckinAccountResult(False, 'CHECKIN_REQUEST_FAILED', 'checkin failed'), None

			user_info_after = get_user_info(
				client, headers, f'{self.provider_config.domain}{self.provider_config.user_info_path}'
			)
			balance_after = extract_balance_summary(user_info_after)
			raw_result_json = {
				'login_user_id': login_user_id,
				'user_info_before': user_info_before,
				'checkin': checkin_response,
				'user_info_after': user_info_after,
			}
			update = CheckinSuccessUpdate(
				checkin_date=(checkin_date or date.today()).isoformat(),
				balance_before=balance_before['quota'] if balance_before else None,
				balance_after=balance_after['quota'] if balance_after else None,
				balance_delta=(
					round(balance_after['quota'] - balance_before['quota'], 2)
					if balance_before and balance_after
					else None
				),
				used_quota_before=balance_before['used_quota'] if balance_before else None,
				used_quota_after=balance_after['used_quota'] if balance_after else None,
				checkin_reward_raw=(checkin_response.get('data') or {}).get('quota_awarded'),
				raw_result_json=json.dumps(raw_result_json, ensure_ascii=False),
			)
			return CheckinAccountResult(True, None), update
		finally:
			client.close()

	def run(
		self,
		*,
		as_of: str | None,
		timezone: str | None,
		dry_run: bool,
		provider_scope: str = WUCUR_PROVIDER,
	) -> CheckinDueSummary:
		from core.application.check_due_accounts_use_case import CheckDueAccountsUseCase

		return CheckDueAccountsUseCase(self).run(
			as_of=as_of,
			timezone=timezone,
			dry_run=dry_run,
			provider_scope=provider_scope,
		)
