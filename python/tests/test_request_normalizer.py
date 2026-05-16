from __future__ import annotations

from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.application.request_normalizer import normalize_command_request


def test_normalize_register_payload():
	request = normalize_command_request(
		{
			'command': 'register',
			'provider': 'wucur',
			'backend': 'sqlite',
			'account': {'name': 'Console User', 'username': 'alice', 'password': 'secret'},
		}
	)

	assert request.command == 'register'
	assert request.account['username'] == 'alice'


def test_normalize_checkin_defaults_scope():
	request = normalize_command_request({'command': 'checkin'})

	assert request.command == 'checkin'
	assert request.scope == 'due'

