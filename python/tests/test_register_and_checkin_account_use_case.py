from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.application.register_and_checkin_account_use_case import RegisterAndCheckinAccountUseCase
from utils.config import AccountConfig, ProviderConfig


@dataclass
class FakeClient:
	calls: list[tuple[str, tuple, dict]]

	def register_account(self, username: str, password: str) -> dict:
		self.calls.append(('register_account', (username, password), {}))
		return {'success': True, 'data': {'username': username}}

	def login_account(self, username: str, password: str) -> dict:
		self.calls.append(('login_account', (username, password), {}))
		return {'success': True, 'data': {'id': 5121}}

	def checkin_account(self, headers: dict, sign_in_url: str) -> dict:
		self.calls.append(('checkin_account', (headers, sign_in_url), {}))
		return {'success': True, 'data': {'quota_awarded': 100}}

	def get_user_info(self, headers: dict, user_info_url: str) -> dict:
		self.calls.append(('get_user_info', (headers, user_info_url), {}))
		return {'success': True, 'quota': 1.0, 'used_quota': 0.5}


def _build_provider() -> ProviderConfig:
	return ProviderConfig(
		name='wucur',
		domain='http://wucur.com:6543',
		login_path='/login',
		login_api_path='/api/user/login',
		sign_in_path='/api/user/checkin',
		user_info_path='/api/user/self',
		api_user_key='new-api-user',
		auth_mode='password_session',
	)


def test_register_and_checkin_use_case_runs_full_flow():
	client = FakeClient(calls=[])
	use_case = RegisterAndCheckinAccountUseCase(client)
	account = AccountConfig(provider='wucur', name='Console User', username='alice@example.com', password='secret')

	result = use_case.run(account, _build_provider())

	assert result.success is True
	assert result.register['success'] is True
	assert result.login['success'] is True
	assert result.checkin['success'] is True
	assert result.user_info['quota'] == 1.0
	assert result.user_info_after_checkin['used_quota'] == 0.5
	assert [item[0] for item in client.calls] == [
		'register_account',
		'login_account',
		'get_user_info',
		'checkin_account',
		'get_user_info',
	]


def test_register_and_checkin_use_case_stops_on_register_failure():
	class FailingClient(FakeClient):
		def register_account(self, username: str, password: str) -> dict:
			self.calls.append(('register_account', (username, password), {}))
			return {'success': False, 'message': 'register failed'}

	client = FailingClient(calls=[])
	use_case = RegisterAndCheckinAccountUseCase(client)
	account = AccountConfig(provider='wucur', name='Console User', username='alice@example.com', password='secret')

	result = use_case.run(account, _build_provider())

	assert result.success is False
	assert result.login is None
	assert [item[0] for item in client.calls] == ['register_account']
