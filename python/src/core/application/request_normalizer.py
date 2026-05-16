"""Normalize command requests for CLI and message ingress."""

from __future__ import annotations

from dataclasses import dataclass


VALID_COMMANDS = {'register', 'list', 'checkin'}
VALID_BACKENDS = {'sqlite', 'worker'}
VALID_SCOPES = {'due'}


@dataclass(frozen=True)
class NormalizedCommandRequest:
	command: str
	provider: str
	backend: str
	scope: str | None = None
	account: dict[str, str] | None = None
	workflow: str | None = None
	target: str | None = None
	callback_url: str | None = None


def normalize_command_request(
	request: dict,
	*,
	default_provider: str = 'wucur',
	default_backend: str = 'sqlite',
	default_scope: str = 'due',
) -> NormalizedCommandRequest:
	command = str(request.get('command', '')).strip().lower()
	if command not in VALID_COMMANDS:
		raise ValueError(f'INVALID_COMMAND: {command}')

	provider = str(request.get('provider', default_provider)).strip() or default_provider
	backend = str(request.get('backend', default_backend)).strip() or default_backend
	if backend not in VALID_BACKENDS:
		raise ValueError(f'INVALID_BACKEND: {backend}')

	scope_value = request.get('scope', default_scope)
	scope = str(scope_value).strip().lower() if scope_value is not None else default_scope
	if command == 'checkin' and scope not in VALID_SCOPES:
		raise ValueError(f'INVALID_SCOPE: {scope}')

	account = request.get('account')
	if command == 'register':
		if not isinstance(account, dict):
			raise ValueError('INVALID_ACCOUNT_PAYLOAD')
		name = str(account.get('name', '')).strip()
		username = str(account.get('username', '')).strip()
		password = str(account.get('password', '')).strip()
		if not name or not username or not password:
			raise ValueError('INVALID_ACCOUNT_PAYLOAD')
		account = {'name': name, 'username': username, 'password': password, 'provider': provider}
	else:
		account = None

	workflow = request.get('workflow')
	workflow = str(workflow).strip() if workflow is not None else None
	target = request.get('target')
	target = str(target).strip() if target is not None else None
	callback_url = request.get('callback_url')
	callback_url = str(callback_url).strip() if callback_url is not None else None

	return NormalizedCommandRequest(
		command=command,
		provider=provider,
		backend=backend,
		scope=scope if command == 'checkin' else None,
		account=account,
		workflow=workflow,
		target=target,
		callback_url=callback_url,
	)
