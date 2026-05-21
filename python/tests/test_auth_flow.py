import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cli.checkin import (
	build_login_payload,
	extract_login_user_id,
	extract_token_from_login_response,
	login_with_bearer_token,
	login_with_session,
)
from core.provider_profile import ProviderProfileResolver
from utils.config import AccountConfig, ProviderConfig, load_accounts_config


class DummyResponse:
	def __init__(self, status_code: int, payload):
		self.status_code = status_code
		self._payload = payload

	def json(self):
		if isinstance(self._payload, Exception):
			raise self._payload
		return self._payload


def test_load_accounts_supports_username_password(monkeypatch):
	monkeypatch.setenv(
		'ANYROUTER_ACCOUNTS',
		json.dumps([{'name': 'Console User', 'provider': 'wucur', 'username': 'alice', 'password': 'secret'}]),
	)

	accounts = load_accounts_config()

	assert accounts is not None
	assert len(accounts) == 1
	assert accounts[0].username == 'alice'
	assert accounts[0].password == 'secret'
	assert accounts[0].cookies is None
	assert accounts[0].api_user is None


def test_build_login_payload():
	account = AccountConfig(username='alice', password='secret')

	assert build_login_payload(account) == {'username': 'alice', 'password': 'secret'}


def test_extract_token_from_login_response_user_root():
	response = DummyResponse(200, {'user': {'token': 'abc123'}})

	assert extract_token_from_login_response(response) == 'abc123'


def test_extract_token_from_login_response_data_user():
	response = DummyResponse(200, {'data': {'user': {'token': 'def456'}}})

	assert extract_token_from_login_response(response) == 'def456'


def test_extract_token_from_login_response_invalid_json():
	response = DummyResponse(200, json.JSONDecodeError('bad', 'doc', 0))

	assert extract_token_from_login_response(response) is None


def test_extract_login_user_id_from_data():
	response = DummyResponse(200, {'data': {'id': 5121}})

	assert extract_login_user_id(response) == '5121'


def test_login_with_bearer_token_success():
	client = MagicMock()
	client.post.return_value = DummyResponse(200, {'user': {'token': 'token-123'}})
	account = AccountConfig(username='alice', password='secret', provider='wucur')
	provider = ProviderConfig(
		name='wucur',
		domain='http://wucur.com:6543',
		login_path='/login',
		login_api_path='/api/user/login',
		auth_mode='bearer_login',
		sign_in_path='/api/user/checkin',
		user_info_path='/api/user/checkin',
		api_user_key=None,
	)

	token = login_with_bearer_token(client, 'Console User', provider, account)

	assert token == 'token-123'
	client.post.assert_called_once()


def test_login_with_bearer_token_requires_credentials():
	client = MagicMock()
	account = AccountConfig(provider='wucur')
	provider = ProviderConfig(
		name='wucur',
		domain='http://wucur.com:6543',
		login_api_path='/api/user/login',
		auth_mode='bearer_login',
		api_user_key=None,
	)

	token = login_with_bearer_token(client, 'Console User', provider, account)

	assert token is None
	client.post.assert_not_called()


def test_login_with_session_success():
	client = MagicMock()
	client.post.return_value = DummyResponse(200, {'success': True, 'data': {'id': 5121}})
	client.cookies = {'session': 'abc123'}
	account = AccountConfig(username='alice', password='secret', provider='wucur')
	provider = ProviderConfig(
		name='wucur',
		domain='http://wucur.com:6543',
		login_path='/login',
		login_api_path='/api/user/login',
		auth_mode='password_session',
		sign_in_path='/api/user/checkin',
		user_info_path='/api/user/self',
		api_user_key='new-api-user',
	)

	user_id = login_with_session(client, 'Console User', provider, account)

	assert user_id == '5121'
	client.post.assert_called_once()


def test_login_with_session_requires_session_cookie():
	client = MagicMock()
	client.post.return_value = DummyResponse(200, {'success': True, 'data': {'id': 5121}})
	client.cookies = {}
	account = AccountConfig(username='alice', password='secret', provider='wucur')
	provider = ProviderConfig(
		name='wucur',
		domain='http://wucur.com:6543',
		login_path='/login',
		login_api_path='/api/user/login',
		auth_mode='password_session',
		api_user_key='new-api-user',
	)

	user_id = login_with_session(client, 'Console User', provider, account)

	assert user_id is None


def test_provider_profile_resolver_resolves_default_profile():
	resolver = ProviderProfileResolver()

	profile = resolver.resolve(None)

	assert profile.name == 'anyrouter'
