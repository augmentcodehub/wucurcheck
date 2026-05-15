#!/usr/bin/env python3
"""
Domain helpers for the checkin-due workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = 'Asia/Shanghai'
DATE_FORMAT = '%Y-%m-%d'


@dataclass(frozen=True)
class StoredAccountRecord:
	record_id: str
	provider: str
	name: str
	username: str
	password: str
	registered_at: str | None = None
	checkin_date: str | None = None
	balance_before: float | None = None
	balance_after: float | None = None
	balance_delta: float | None = None
	used_quota_before: float | None = None
	used_quota_after: float | None = None
	checkin_reward_raw: int | None = None
	last_status: str | None = None
	raw_result_json: str | None = None


@dataclass(frozen=True)
class CheckinDuePlanItem:
	record: StoredAccountRecord
	parsed_checkin_date: date | None
	state: str
	reason: str


@dataclass(frozen=True)
class CheckinSuccessUpdate:
	checkin_date: str
	balance_before: float | None = None
	balance_after: float | None = None
	balance_delta: float | None = None
	used_quota_before: float | None = None
	used_quota_after: float | None = None
	checkin_reward_raw: int | None = None
	last_status: str = 'checkin_success'
	raw_result_json: str = ''


@dataclass(frozen=True)
class CheckinDueSummary:
	scanned: int = 0
	due: int = 0
	skipped: int = 0
	succeeded: int = 0
	failed: int = 0
	exit_code: int = 0
	error_code: str | None = None


def parse_checkin_date(value: str | None) -> date | None:
	if value is None:
		return None
	text = value.strip()
	if not text:
		return None
	return datetime.strptime(text, DATE_FORMAT).date()


def normalize_timezone(timezone_name: str | None) -> ZoneInfo:
	name = (timezone_name or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
	try:
		return ZoneInfo(name)
	except ZoneInfoNotFoundError:
		if name == DEFAULT_TIMEZONE:
			return timezone(timedelta(hours=8), DEFAULT_TIMEZONE)
		raise


def resolve_as_of_date(as_of: str | None, timezone_name: str | None) -> date:
	if as_of is not None:
		return datetime.strptime(as_of.strip(), DATE_FORMAT).date()
	tz = normalize_timezone(timezone_name)
	return datetime.now(tz).date()


def classify_due_accounts(
	accounts: list[StoredAccountRecord],
	as_of_date: date,
	provider_scope: str = 'wucur',
) -> tuple[list[CheckinDuePlanItem], list[CheckinDuePlanItem], list[CheckinDuePlanItem]]:
	due_items: list[CheckinDuePlanItem] = []
	skipped_items: list[CheckinDuePlanItem] = []
	invalid_items: list[CheckinDuePlanItem] = []

	for record in accounts:
		if record.provider != provider_scope:
			invalid_items.append(
				CheckinDuePlanItem(
					record=record,
					parsed_checkin_date=None,
					state='invalid',
					reason=f'unsupported provider: {record.provider}',
				)
			)
			continue

		try:
			parsed_date = parse_checkin_date(record.checkin_date)
		except ValueError:
			invalid_items.append(
				CheckinDuePlanItem(
					record=record,
					parsed_checkin_date=None,
					state='invalid',
					reason=f'invalid checkin_date: {record.checkin_date}',
				)
			)
			continue

		if parsed_date is None:
			due_items.append(
				CheckinDuePlanItem(
					record=record,
					parsed_checkin_date=None,
					state='due',
					reason='missing checkin_date',
				)
			)
			continue

		if parsed_date < as_of_date:
			due_items.append(
				CheckinDuePlanItem(
					record=record,
					parsed_checkin_date=parsed_date,
					state='due',
					reason=f'checkin_date {parsed_date.isoformat()} is before {as_of_date.isoformat()}',
				)
			)
		else:
			skipped_items.append(
				CheckinDuePlanItem(
					record=record,
					parsed_checkin_date=parsed_date,
					state='skipped',
					reason=f'checkin_date {parsed_date.isoformat()} is not before {as_of_date.isoformat()}',
				)
			)

	return due_items, skipped_items, invalid_items


def build_success_update(
	*,
	checkin_date: date,
	balance_before: float | None = None,
	balance_after: float | None = None,
	used_quota_before: float | None = None,
	used_quota_after: float | None = None,
	checkin_reward_raw: int | None = None,
	raw_result_json: str = '',
) -> CheckinSuccessUpdate:
	balance_delta = None
	if balance_before is not None and balance_after is not None:
		balance_delta = round(balance_after - balance_before, 2)

	return CheckinSuccessUpdate(
		checkin_date=checkin_date.isoformat(),
		balance_before=balance_before,
		balance_after=balance_after,
		balance_delta=balance_delta,
		used_quota_before=used_quota_before,
		used_quota_after=used_quota_after,
		checkin_reward_raw=checkin_reward_raw,
		raw_result_json=raw_result_json,
	)
