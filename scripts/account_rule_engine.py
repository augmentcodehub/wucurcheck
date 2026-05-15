#!/usr/bin/env python3
"""
Reusable account generation rule engine.

This module is independent from any registration logic and can be reused
for other testing scenarios that need rule-based username/password generation.
"""

from __future__ import annotations

import json
import random
import re
import string
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class AccountRuleConfig:
	name_prefix: str = '账号'
	email_prefix: str = 'user'
	email_domain: str = 'example.com'
	password: str = '123Claude&Codex'
	timestamp_format: str = '%m%d%H%M%S'
	random_length: int = 0
	separator: str = ''
	seed_template: str = '{time}{rand}'
	name_template: str = '{name_prefix}{seed}'
	email_local_template: str = '{email_prefix}{separator}{seed}'
	name_regex: str = ''
	name_replacement: str = ''
	email_local_regex: str = ''
	email_local_replacement: str = ''
	password_template: str = '{password}'
	password_regex: str = ''
	password_replacement: str = ''
	sequence_start: int = 1
	sequence_width: int = 0
	count: int = 1
	provider: str = 'wucur'
	skip_checkin: bool = True
	json_output: bool = False

	@classmethod
	def from_dict(cls, data: dict) -> 'AccountRuleConfig':
		return cls(
			name_prefix=str(data.get('name_prefix', '账号')),
			email_prefix=str(data.get('email_prefix', 'user')),
			email_domain=str(data.get('email_domain', 'example.com')),
			password=str(data.get('password', '123Claude&Codex')),
			timestamp_format=str(data.get('timestamp_format', '%m%d%H%M%S')),
			random_length=int(data.get('random_length', 0)),
			separator=str(data.get('separator', '')),
			seed_template=str(data.get('seed_template', '{time}{rand}')),
			name_template=str(data.get('name_template', '{name_prefix}{seed}')),
			email_local_template=str(data.get('email_local_template', '{email_prefix}{separator}{seed}')),
			name_regex=str(data.get('name_regex', '')),
			name_replacement=str(data.get('name_replacement', '')),
			email_local_regex=str(data.get('email_local_regex', '')),
			email_local_replacement=str(data.get('email_local_replacement', '')),
			password_template=str(data.get('password_template', '{password}')),
			password_regex=str(data.get('password_regex', '')),
			password_replacement=str(data.get('password_replacement', '')),
			sequence_start=int(data.get('sequence_start', 1)),
			sequence_width=int(data.get('sequence_width', 0)),
			count=int(data.get('count', 1)),
			provider=str(data.get('provider', 'wucur')),
			skip_checkin=bool(data.get('skip_checkin', True)),
			json_output=bool(data.get('json_output', False)),
		)


def load_rule_config(path: Path) -> AccountRuleConfig:
	if not path.exists():
		raise ValueError(f'Config file not found: {path}')
	try:
		data = json.loads(path.read_text(encoding='utf-8'))
	except json.JSONDecodeError as exc:
		raise ValueError(f'Invalid JSON in {path}: {exc}') from exc
	if not isinstance(data, dict):
		raise ValueError(f'{path} must contain a JSON object')
	return AccountRuleConfig.from_dict(data)


def write_example_rule_config(path: Path) -> None:
	example = {
		'name_prefix': '账号',
		'email_prefix': 'user',
		'email_domain': 'example.com',
		'password': '123Claude&Codex',
		'timestamp_format': '%m%d%H%M%S',
		'random_length': 0,
		'separator': '',
		'seed_template': '{seq}_{time}{rand}',
		'name_template': '{name_prefix}{seed}',
		'email_local_template': '{email_prefix}{separator}{seed}',
		'name_regex': '',
		'name_replacement': '',
		'email_local_regex': '',
		'email_local_replacement': '',
		'password_template': '{password}',
		'password_regex': '',
		'password_replacement': '',
		'sequence_start': 1,
		'sequence_width': 2,
		'count': 10,
		'provider': 'wucur',
	}
	path.write_text(json.dumps(example, ensure_ascii=False, indent=2), encoding='utf-8')


def render_template(template: str, variables: dict[str, str]) -> str:
	result = template
	for key, value in variables.items():
		result = result.replace(f'{{{key}}}', value)
	return result


def apply_regex_rule(source: str, pattern: str, replacement: str, field_name: str) -> str:
	if not pattern:
		return source
	try:
		regex = re.compile(pattern)
	except re.error as exc:
		raise ValueError(f'Invalid regex for {field_name}: {exc}') from exc
	result = regex.sub(replacement, source)
	if result == source and not regex.search(source):
		raise ValueError(f'Regex for {field_name} did not match: {source}')
	return result


def _generate_random_part(length: int) -> str:
	if length <= 0:
		return ''
	alphabet = string.ascii_lowercase + string.digits
	return ''.join(random.choice(alphabet) for _ in range(length))


def _format_sequence(index: int, width: int) -> str:
	if width > 0:
		return str(index).zfill(width)
	return str(index)


def build_account_from_rule(config: AccountRuleConfig, index: int) -> dict[str, str]:
	if not config.email_domain:
		raise ValueError('email_domain is required')
	if not config.password:
		raise ValueError('password is required')

	time_part = datetime.now().strftime(config.timestamp_format) if config.timestamp_format else ''
	random_part = _generate_random_part(config.random_length)
	sequence = _format_sequence(config.sequence_start + index, config.sequence_width)

	template_vars = {
		'name_prefix': config.name_prefix,
		'email_prefix': config.email_prefix,
		'email_domain': config.email_domain,
		'separator': config.separator,
		'time': time_part,
		'rand': random_part,
		'seq': sequence,
		'password': config.password,
	}
	seed = render_template(config.seed_template, template_vars)
	template_vars['seed'] = seed

	name = render_template(config.name_template, template_vars)
	name = apply_regex_rule(name, config.name_regex, config.name_replacement, 'name')

	email_local = render_template(config.email_local_template, template_vars)
	email_local = apply_regex_rule(
		email_local, config.email_local_regex, config.email_local_replacement, 'email_local'
	)

	password = render_template(config.password_template, template_vars)
	password = apply_regex_rule(password, config.password_regex, config.password_replacement, 'password')

	return {
		'sequence': sequence,
		'seed': seed,
		'name': name,
		'provider': config.provider,
		'username': f'{email_local}@{config.email_domain}',
		'password': password,
	}


def generate_accounts(config: AccountRuleConfig) -> list[dict[str, str]]:
	return [build_account_from_rule(config, index) for index in range(config.count)]
