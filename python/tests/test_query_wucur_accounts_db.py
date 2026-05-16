from __future__ import annotations

from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from adapters.persistence.sqlite.account_registry_db import connect_db, ensure_schema, upsert_registered_account
from cli.query_wucur_accounts_db import fetch_rows, print_table


def _create_temp_db(tmp_path: Path) -> Path:
	db_path = tmp_path / 'query.sqlite3'
	conn = connect_db(db_path)
	try:
		ensure_schema(conn)
		upsert_registered_account(
			conn,
			name='Console User',
			provider='wucur',
			username='alice@example.com',
			password='secret',
			registered_at='2026-05-15T10:00:00',
			checkin_date='2026-05-15',
			balance_before=1.0,
			balance_after=2.0,
			balance_delta=1.0,
			used_quota_before=0.2,
			used_quota_after=0.1,
			checkin_reward_raw=100,
			last_status='checkin_success',
			raw_result_json='{}',
		)
	finally:
		conn.close()
	return db_path


def test_fetch_rows_returns_latest_record(tmp_path):
	db_path = _create_temp_db(tmp_path)
	conn = connect_db(db_path)
	try:
		rows = fetch_rows(conn, 10)
	finally:
		conn.close()

	assert len(rows) == 1
	assert rows[0]['username'] == 'alice@example.com'


def test_print_table_emits_expected_headers(capsys, tmp_path):
	db_path = _create_temp_db(tmp_path)
	conn = connect_db(db_path)
	try:
		rows = fetch_rows(conn, 10)
	finally:
		conn.close()

	print_table(rows)
	output = capsys.readouterr().out

	assert '用户名' in output
	assert '注册时间' in output
