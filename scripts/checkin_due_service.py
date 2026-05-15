#!/usr/bin/env python3
"""
Batch check-in service for due Wucur accounts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from .checkin_due_domain import (
	CheckinDueSummary,
	CheckinSuccessUpdate,
	StoredAccountRecord,
	build_success_update,
	classify_due_accounts,
	resolve_as_of_date,
)
from .checkin_due_repository import CheckinDueError, CheckinDueRepository
from .wucur_client import checkin_account, extract_balance_summary, get_user_info, login_with_session
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
			raw_result_json = json.dumps(
				{
					'login_user_id': login_user_id,
					'user_info_before': user_info_before,
					'checkin': checkin_response,
					'user_info_after': user_info_after,
				},
				ensure_ascii=False,
			)
			update = build_success_update(
				checkin_date=checkin_date or date.today(),
				balance_before=balance_before['quota'] if balance_before else None,
				balance_after=balance_after['quota'] if balance_after else None,
				used_quota_before=balance_before['used_quota'] if balance_before else None,
				used_quota_after=balance_after['used_quota'] if balance_after else None,
				checkin_reward_raw=(checkin_response.get('data') or {}).get('quota_awarded'),
				raw_result_json=raw_result_json,
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
		as_of_date = resolve_as_of_date(as_of, timezone)
		records = self.repository.list_accounts(provider_scope)
		due_items, skipped_items, invalid_items = classify_due_accounts(records, as_of_date, provider_scope=provider_scope)

		if dry_run:
			exit_code = 0 if not invalid_items else 1
			return CheckinDueSummary(
				scanned=len(records),
				due=len(due_items),
				skipped=len(skipped_items),
				succeeded=0,
				failed=len(invalid_items),
				exit_code=exit_code,
				error_code='INVALID_DATE_FORMAT' if invalid_items else None,
			)

		succeeded = 0
		failed = len(invalid_items)
		error_code = 'INVALID_DATE_FORMAT' if invalid_items else None

		for item in due_items:
			result, update = self.run_account_checkin(item.record, checkin_date=as_of_date)
			if result.success and update is not None:
				try:
					final_update = CheckinSuccessUpdate(
						checkin_date=as_of_date.isoformat(),
						balance_before=update.balance_before,
						balance_after=update.balance_after,
						balance_delta=update.balance_delta,
						used_quota_before=update.used_quota_before,
						used_quota_after=update.used_quota_after,
						checkin_reward_raw=update.checkin_reward_raw,
						last_status=update.last_status,
						raw_result_json=update.raw_result_json,
					)
					self.repository.save_checkin_success(item.record.record_id, final_update)
				except CheckinDueError:
					failed += 1
					error_code = 'BACKEND_WRITE_FAILED'
				else:
					succeeded += 1
			else:
				failed += 1
				error_code = result.error_code or error_code or 'CHECKIN_REQUEST_FAILED'

		exit_code = 0 if failed == 0 else 1
		return CheckinDueSummary(
			scanned=len(records),
			due=len(due_items),
			skipped=len(skipped_items),
			succeeded=succeeded,
			failed=failed,
			exit_code=exit_code,
			error_code=error_code,
		)
