from __future__ import annotations

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.provider_profile import ProviderProfileResolver


def test_resolve_defaults_to_anyrouter():
	resolver = ProviderProfileResolver()
	profile = resolver.resolve(None)

	assert profile.name == 'anyrouter'
	assert profile.domain == 'https://anyrouter.top'


def test_resolve_supports_explicit_provider():
	resolver = ProviderProfileResolver()
	profile = resolver.resolve('wucur')

	assert profile.name == 'wucur'
	assert profile.login_api_path == '/api/user/login'


def test_resolve_supports_env_override(monkeypatch):
	monkeypatch.setenv(
		'PROVIDERS',
		json.dumps({'wucur': {'domain': 'https://example.com', 'login_api_path': '/login/api'}}),
	)

	resolver = ProviderProfileResolver()
	profile = resolver.resolve('wucur')

	assert profile.domain == 'https://example.com'
	assert profile.login_api_path == '/login/api'
