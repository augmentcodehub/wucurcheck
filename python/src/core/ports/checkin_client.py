"""Check-in client port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from utils.config import AccountConfig, ProviderConfig


@runtime_checkable
class CheckinClient(Protocol):
	def login_account(self, username: str, password: str) -> dict:
		...

	def register_account(self, username: str, password: str) -> dict:
		...

	def checkin_account(self, headers: dict, sign_in_url: str) -> dict:
		...

	def get_user_info(self, headers: dict, user_info_url: str) -> dict:
		...

	def login_with_session(
		self,
		account_name: str,
		provider_config: ProviderConfig,
		account: AccountConfig,
	) -> str | None:
		...
