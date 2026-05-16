"""Provider/profile abstraction for site-specific defaults and capabilities."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os


@dataclass(frozen=True)
class ProviderProfile:
	name: str
	domain: str
	login_path: str = '/login'
	login_api_path: str | None = None
	sign_in_path: str | None = '/api/user/sign_in'
	user_info_path: str | None = '/api/user/self'
	api_user_key: str | None = 'new-api-user'
	auth_mode: str = 'cookie'
	bypass_method: str | None = None
	waf_cookie_names: list[str] | None = None

	def needs_waf_cookies(self) -> bool:
		return self.bypass_method == 'waf_cookies'

	def needs_manual_check_in(self) -> bool:
		return self.sign_in_path is not None

	def uses_bearer_login(self) -> bool:
		return self.auth_mode == 'bearer_login'

	def uses_password_session(self) -> bool:
		return self.auth_mode == 'password_session'


class ProviderProfileResolver:
	def __init__(self, profiles: dict[str, ProviderProfile] | None = None):
		self._profiles = profiles or _default_profiles()

	def resolve(self, provider_name: str | None) -> ProviderProfile:
		name = (provider_name or 'anyrouter').strip() or 'anyrouter'
		overrides = self._load_overrides()
		if name in overrides:
			return overrides[name]
		profile = self._profiles.get(name)
		if profile is None:
			raise KeyError(f'UNSUPPORTED_PROVIDER: {name}')
		return profile

	def _load_overrides(self) -> dict[str, ProviderProfile]:
		raw = os.getenv('PROVIDERS')
		if not raw:
			return {}
		try:
			payload = json.loads(raw)
		except json.JSONDecodeError:
			return {}
		if not isinstance(payload, dict):
			return {}
		overrides: dict[str, ProviderProfile] = {}
		for name, data in payload.items():
			if not isinstance(data, dict) or 'domain' not in data:
				continue
			overrides[name] = ProviderProfile(
				name=name,
				domain=data['domain'],
				login_path=data.get('login_path', '/login'),
				login_api_path=data.get('login_api_path'),
				sign_in_path=data.get('sign_in_path', '/api/user/sign_in'),
				user_info_path=data.get('user_info_path', '/api/user/self'),
				api_user_key=data.get('api_user_key', 'new-api-user'),
				auth_mode=data.get('auth_mode', 'cookie'),
				bypass_method=data.get('bypass_method'),
				waf_cookie_names=data.get('waf_cookie_names'),
			)
		return overrides


def _default_profiles() -> dict[str, ProviderProfile]:
	return {
		'anyrouter': ProviderProfile(
			name='anyrouter',
			domain='https://anyrouter.top',
			login_path='/login',
			login_api_path=None,
			sign_in_path='/api/user/sign_in',
			user_info_path='/api/user/self',
			api_user_key='new-api-user',
			auth_mode='cookie',
			bypass_method='waf_cookies',
			waf_cookie_names=['acw_tc', 'cdn_sec_tc', 'acw_sc__v2'],
		),
		'agentrouter': ProviderProfile(
			name='agentrouter',
			domain='https://agentrouter.org',
			login_path='/login',
			login_api_path=None,
			sign_in_path=None,
			user_info_path='/api/user/self',
			api_user_key='new-api-user',
			auth_mode='cookie',
			bypass_method='waf_cookies',
			waf_cookie_names=['acw_tc'],
		),
		'wucur': ProviderProfile(
			name='wucur',
			domain='http://wucur.com:6543',
			login_path='/login',
			login_api_path='/api/user/login',
			sign_in_path='/api/user/checkin',
			user_info_path='/api/user/self',
			api_user_key='new-api-user',
			auth_mode='password_session',
			bypass_method=None,
			waf_cookie_names=None,
		),
	}
