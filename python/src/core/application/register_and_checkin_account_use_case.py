"""Application use case for register + login + optional check-in."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from core.domain import CheckinSuccessUpdate
from core.ports.account_repository import AccountRepository
from core.ports.checkin_client import CheckinClient
from utils.config import AccountConfig, ProviderConfig


@dataclass(frozen=True)
class RegisterAndCheckinResult:
	success: bool
	register: dict | None
	login: dict | None
	checkin: dict | None
	user_info: dict | None
	user_info_after_checkin: dict | None
	message: str | None = None


class RegisterAndCheckinAccountUseCase:
	def __init__(self, client: CheckinClient, repository: AccountRepository | None = None):
		self.client = client
		self.repository = repository

	def run(
		self,
		account: AccountConfig,
		provider: ProviderConfig,
		*,
		skip_checkin: bool = False,
		skip_balance: bool = False,
	) -> RegisterAndCheckinResult:
		register_data = self.client.register_account(account.username or '', account.password or '')
		if not register_data.get('success'):
			return RegisterAndCheckinResult(False, register_data, None, None, None, None, 'register failed')

		login_data = self.client.login_account(account.username or '', account.password or '')
		if not login_data.get('success'):
			return RegisterAndCheckinResult(False, register_data, login_data, None, None, None, 'login failed')

		user_id = _extract_user_id(login_data)
		headers = _build_authenticated_headers(user_id, provider) if user_id else None
		user_info = None
		if headers and not skip_balance:
			user_info = self.client.get_user_info(headers, f'{provider.domain}{provider.user_info_path}')

		checkin_data = None
		user_info_after = None
		if not skip_checkin and headers is not None:
			checkin_data = self.client.checkin_account(headers, f'{provider.domain}{provider.sign_in_path}')
			if not skip_balance:
				user_info_after = self.client.get_user_info(headers, f'{provider.domain}{provider.user_info_path}')

		if self.repository is not None:
			self._persist_local_record(account, provider, register_data, login_data, checkin_data, user_info, user_info_after)

		return RegisterAndCheckinResult(True, register_data, login_data, checkin_data, user_info, user_info_after)

	def _persist_local_record(
		self,
		account: AccountConfig,
		provider: ProviderConfig,
		register_data: dict,
		login_data: dict,
		checkin_data: dict | None,
		user_info: dict | None,
		user_info_after: dict | None,
	) -> None:
		if self.repository is None:
			return
		payload = {
			'register': register_data,
			'login': login_data,
			'checkin': checkin_data,
			'user_info': user_info,
			'user_info_after_checkin': user_info_after,
		}
		# Local persistence continues to be handled by the legacy scripts.
		_ = payload


def _build_authenticated_headers(user_id: str, provider: ProviderConfig) -> dict[str, str]:
	headers = {
		'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
		'Accept': 'application/json, text/plain, */*',
		'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
		'Accept-Encoding': 'gzip, deflate, br, zstd',
		'Referer': provider.domain,
		'Origin': provider.domain,
		'Connection': 'keep-alive',
		'Sec-Fetch-Dest': 'empty',
		'Sec-Fetch-Mode': 'cors',
		'Sec-Fetch-Site': 'same-origin',
	}
	if provider.api_user_key and user_id:
		headers[provider.api_user_key] = user_id
	return headers


def _extract_user_id(login_data: dict) -> str | None:
	data_node = login_data.get('data')
	if isinstance(data_node, dict) and data_node.get('id') is not None:
		return str(data_node.get('id'))
	user = login_data.get('user')
	if isinstance(user, dict) and user.get('id') is not None:
		return str(user.get('id'))
	return None
