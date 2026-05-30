"""wucur register — register accounts via wucur or kiro provider."""
import json
import os
import random
import string
import subprocess
import time
from pathlib import Path

import httpx
import typer

from lib.constants import DEFAULT_PASSWORD


def register(
	provider: str = typer.Option(..., '--provider', help='Provider: wucur or kiro'),
	count: int = typer.Option(1, '--count', help='Number of accounts to register'),
	output: Path = typer.Option('results.json', '--output', help='Output results.json path'),
	email_domain: str = typer.Option('ouraihub.com', '--email-domain', help='Email domain for kiro'),
):
	"""Register new accounts via wucur or kiro provider."""
	if provider == 'wucur':
		results = _register_wucur(count)
	elif provider == 'kiro':
		results = _register_kiro(count, email_domain)
	else:
		typer.echo(f'Error: unknown provider {provider}', err=True)
		raise typer.Exit(1)

	output.parent.mkdir(parents=True, exist_ok=True)
	output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
	typer.echo(f'Registered {len(results)} account(s) → {output}')


def _generate_email() -> str:
	prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
	return f'{prefix}@qq.com'


def _register_wucur(count: int) -> list[dict]:
	domain = os.environ.get('WUCUR_DOMAIN', 'http://wucur.com:6543')
	password = os.environ.get('PASSWORD', DEFAULT_PASSWORD)
	results = []

	with httpx.Client(http2=True, timeout=30) as client:
		for i in range(count):
			username = _generate_email()
			try:
				resp = client.post(
					f'{domain}/api/user/register',
					json={'username': username, 'password': password},
					headers={'Content-Type': 'application/json'},
					timeout=30,
				)
				data = resp.json() if resp.status_code == 200 else {}
				if resp.status_code == 200 and data.get('success'):
					results.append({
						'username': username,
						'password': password,
						'platform': 'wucur',
						'status': 'active',
						'last_result': '注册成功',
						'register_source': 'github',
					})
				else:
					msg = data.get('message', f'HTTP {resp.status_code}')
					results.append({'username': username, 'status': 'active', 'last_result': f'注册失败: {msg}'})
			except Exception as e:
				results.append({'username': username, 'status': 'active', 'last_result': f'异常: {str(e)[:80]}'})

			if i < count - 1:
				time.sleep(random.randint(2, 5))

	return results


def _register_kiro(count: int, email_domain: str) -> list[dict]:
	email_api_key = os.environ.get('EMAIL_API_KEY', '')
	if not email_api_key:
		typer.echo('Error: EMAIL_API_KEY not set', err=True)
		raise typer.Exit(1)

	node_register_dir = Path(__file__).resolve().parents[3] / 'node-register'
	if not (node_register_dir / 'dist' / 'index.js').exists():
		typer.echo(f'Error: node-register not built at {node_register_dir}', err=True)
		raise typer.Exit(1)

	tmp_output = Path('/tmp/kiro_register_output.json')
	cmd = [
		'node', str(node_register_dir / 'dist' / 'index.js'),
		'--email-api-key', email_api_key,
		'--email-domain', email_domain,
		'--count', str(count),
		'--output', str(tmp_output),
	]

	try:
		proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
	except subprocess.TimeoutExpired:
		return [{'username': 'unknown', 'status': 'active', 'last_result': 'Node 注册超时'}]

	if not tmp_output.exists():
		return [{'username': 'unknown', 'status': 'active', 'last_result': f'Node 注册失败: {proc.stderr[:200]}'}]

	node_results = json.loads(tmp_output.read_text(encoding='utf-8'))
	results = []
	for r in node_results:
		if r.get('status') == 'success':
			results.append({
				'username': r.get('email', ''),
				'password': r.get('password', ''),
				'platform': 'kiro',
				'status': 'active',
				'last_result': '注册成功',
				'register_source': 'github',
			})
		else:
			results.append({
				'username': r.get('email', 'unknown'),
				'status': 'active',
				'last_result': f"注册失败: {r.get('error', 'unknown')}",
			})

	return results
