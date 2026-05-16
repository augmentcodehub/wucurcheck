from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from adapters.persistence.sqlite.account_registry_db import connect_db, ensure_schema
from tools.register.register_one_account_to_db import extract_balance
from tools.register.register_one_account_to_db import persist_success


def test_extract_balance_supports_summary_payload():
	user_info = {'success': True, 'quota': 1.92, 'used_quota': 0.0}

	assert extract_balance(user_info) == (1.92, 0.0)


def test_extract_balance_supports_raw_payload():
	user_info = {'success': True, 'data': {'quota': 960000, 'used_quota': 0}}

	assert extract_balance(user_info) == (1.92, 0.0)


def test_persist_success_writes_sqlite(tmp_path):
	db_path = tmp_path / 'accounts.sqlite3'
	conn = connect_db(db_path)
	try:
		ensure_schema(conn)
	finally:
		conn.close()

	payload = {
		'register': {'success': True},
		'login': {'success': True},
		'checkin': {'success': True, 'data': {'quota_awarded': 100}},
		'user_info': {'success': True, 'quota': 1.0, 'used_quota': 0.5},
		'user_info_after_checkin': {'success': True, 'quota': 1.5, 'used_quota': 0.4},
	}

	persist_success({'name': 'Console User', 'provider': 'wucur', 'username': 'alice@example.com', 'password': 'secret'}, payload, db_path)

	conn = connect_db(db_path)
	try:
		row = conn.execute('SELECT username, last_status FROM registered_accounts WHERE username = ?', ('alice@example.com',)).fetchone()
	finally:
		conn.close()

	assert row['username'] == 'alice@example.com'
	assert row['last_status'] == 'checkin_success'
