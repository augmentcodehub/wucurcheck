from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.domain import (
	CheckinDuePlanItem,
	CheckinDueSummary,
	StoredAccountRecord,
	build_success_update,
	classify_due_accounts,
	parse_checkin_date,
	resolve_as_of_date,
)


def test_parse_checkin_date_supports_null_and_iso():
	assert parse_checkin_date(None) is None
	assert parse_checkin_date('') is None
	assert parse_checkin_date('2026-05-14') == date(2026, 5, 14)


def test_parse_checkin_date_rejects_invalid_format():
	try:
		parse_checkin_date('2026/05/14')
	except ValueError:
		assert True
	else:
		raise AssertionError('expected ValueError')


def test_resolve_as_of_date_parses_explicit_date():
	assert resolve_as_of_date('2026-05-14', 'Asia/Shanghai') == date(2026, 5, 14)


def test_classify_due_accounts_splits_due_skip_and_invalid():
	accounts = [
		StoredAccountRecord(record_id='1', provider='wucur', name='A', username='a', password='p', checkin_date='2026-05-13'),
		StoredAccountRecord(record_id='2', provider='wucur', name='B', username='b', password='p', checkin_date='2026-05-14'),
		StoredAccountRecord(record_id='3', provider='wucur', name='C', username='c', password='p', checkin_date=None),
		StoredAccountRecord(record_id='4', provider='wucur', name='D', username='d', password='p', checkin_date='2026/05/14'),
		StoredAccountRecord(record_id='5', provider='other', name='E', username='e', password='p', checkin_date='2026-05-13'),
	]

	due_items, skipped_items, invalid_items = classify_due_accounts(accounts, date(2026, 5, 14))

	assert [item.record.record_id for item in due_items] == ['1', '3']
	assert [item.record.record_id for item in skipped_items] == ['2']
	assert [item.record.record_id for item in invalid_items] == ['4', '5']
	assert all(isinstance(item, CheckinDuePlanItem) for item in due_items + skipped_items + invalid_items)


def test_build_success_update_computes_balance_delta():
	update = build_success_update(
		checkin_date=date(2026, 5, 14),
		balance_before=1.0,
		balance_after=2.25,
		used_quota_before=0.5,
		used_quota_after=0.75,
		checkin_reward_raw=123,
		raw_result_json='{}',
	)

	assert update.checkin_date == '2026-05-14'
	assert update.balance_delta == 1.25
	assert update.checkin_reward_raw == 123


def test_summary_defaults_are_zero():
	summary = CheckinDueSummary()

	assert summary.scanned == 0
	assert summary.due == 0
	assert summary.skipped == 0
	assert summary.succeeded == 0
	assert summary.failed == 0
	assert summary.exit_code == 0
	assert summary.error_code is None
