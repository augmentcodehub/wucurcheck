from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.register_one_account_to_db import extract_balance


def test_extract_balance_supports_summary_payload():
	user_info = {'success': True, 'quota': 1.92, 'used_quota': 0.0}

	assert extract_balance(user_info) == (1.92, 0.0)


def test_extract_balance_supports_raw_payload():
	user_info = {'success': True, 'data': {'quota': 960000, 'used_quota': 0}}

	assert extract_balance(user_info) == (1.92, 0.0)
