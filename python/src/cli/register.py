"""wucur register — register accounts via provider registry."""
import json
import os
import random
import string
import time
from pathlib import Path

import httpx
import typer

from core.result_record import ResultRecord
from lib.constants import DEFAULT_PASSWORD
from providers import get_provider
from utils.logger import get_logger

log = get_logger('cli.register')


def register(
	provider: str = typer.Option(..., '--provider', help='Provider: wucur or kiro'),
	count: int = typer.Option(1, '--count', help='Number of accounts to register'),
	output: Path = typer.Option('results.json', '--output', help='Output results.json path'),
	email_domain: str = typer.Option('ouraihub.com', '--email-domain', help='Email domain for kiro'),
):
	"""Register new accounts via wucur or kiro provider."""
	log.info('Register start', extra={'provider': provider, 'count': count})

	p = get_provider(provider)
	if not p:
		log.error('Unknown provider', extra={'provider': provider})
		typer.echo(f'Error: unknown provider {provider}', err=True)
		raise typer.Exit(1)

	if provider == 'wucur':
		results = _register_wucur(p, count)
	elif provider == 'kiro':
		results = _register_kiro(p, count, email_domain)
	else:
		results = []

	output.parent.mkdir(parents=True, exist_ok=True)
	output.write_text(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2), encoding='utf-8')
	log.info('Register done', extra={'count': len(results), 'output': str(output)})
	typer.echo(f'Registered {len(results)} account(s) → {output}')


def _generate_email() -> str:
	prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
	return f'{prefix}@qq.com'


def _register_wucur(provider, count: int) -> list[ResultRecord]:
	password = os.environ.get('PASSWORD', DEFAULT_PASSWORD)
	results: list[ResultRecord] = []

	with httpx.Client(http2=True, timeout=30) as client:
		for i in range(count):
			username = _generate_email()
			result = provider.register(client, username, password)
			if result.success:
				results.append(ResultRecord(
					username=username, password=password, platform='wucur',
					last_result='注册成功', register_source='github',
				))
			else:
				results.append(ResultRecord(username=username, last_result=f'注册失败: {result.message}'))
			if i < count - 1:
				time.sleep(random.randint(2, 5))

	return results


def _register_kiro(provider, count: int, email_domain: str) -> list[ResultRecord]:
	result = provider.register('', '', email_domain=email_domain, count=count)
	if not result.success:
		return [ResultRecord(username='unknown', last_result=f'注册失败: {result.message}')]

	records: list[ResultRecord] = []
	for r in result.data.get('node_results', []):
		if r.get('status') == 'success':
			records.append(ResultRecord(
				username=r.get('email', ''), password=r.get('password', ''),
				platform='kiro', last_result='注册成功', register_source='github',
			))
		else:
			records.append(ResultRecord(
				username=r.get('email', 'unknown'),
				last_result=f"注册失败: {r.get('error', 'unknown')}",
			))
	return records
