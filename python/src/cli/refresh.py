"""wucur refresh — refresh kiro OIDC tokens via Cloudflare KV."""
import json
import os
from pathlib import Path
from typing import Optional

import httpx
import typer


def refresh(
	target: Optional[str] = typer.Option(None, '--target', help='Single account email to refresh'),
	all_accounts: bool = typer.Option(False, '--all', help='Refresh all kiro accounts'),
	output: Path = typer.Option('results.json', '--output', help='Output results.json path'),
):
	"""Refresh kiro OIDC tokens from Cloudflare KV."""
	cf_account_id = os.environ.get('CF_ACCOUNT_ID', '')
	cf_api_token = os.environ.get('CF_API_TOKEN', '')
	kv_namespace_id = os.environ.get('KV_NAMESPACE_ID', '')

	if not cf_account_id or not cf_api_token or not kv_namespace_id:
		typer.echo('Error: CF_ACCOUNT_ID, CF_API_TOKEN, KV_NAMESPACE_ID required', err=True)
		raise typer.Exit(1)

	if not target and not all_accounts:
		typer.echo('Error: provide --target or --all', err=True)
		raise typer.Exit(1)

	kv_base = f'https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/storage/kv/namespaces/{kv_namespace_id}'
	cf_headers = {'Authorization': f'Bearer {cf_api_token}'}

	with httpx.Client(http2=True, timeout=30) as client:
		if target:
			keys = [f'account:{target}']
		else:
			keys = _kv_list_accounts(client, kv_base, cf_headers)

		results = []
		for key in keys:
			account = _kv_get(client, kv_base, cf_headers, key)
			if not account or account.get('platform') != 'kiro' or not account.get('refresh_token'):
				continue

			username = account.get('username', '')
			r = _refresh_oidc(client, account)
			if r['success']:
				results.append({
					'username': username,
					'status': 'active',
					'refreshToken': r['refreshToken'],
					'accessToken': r['accessToken'],
					'last_result': 'Token 刷新成功',
				})
			else:
				results.append({
					'username': username,
					'status': 'active',
					'last_result': f"刷新失败: {r['error']}",
				})

	output.parent.mkdir(parents=True, exist_ok=True)
	output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
	typer.echo(f'Refresh done: {len(results)} account(s) → {output}')


def _kv_list_accounts(client: httpx.Client, kv_base: str, headers: dict) -> list[str]:
	keys = []
	cursor = None
	while True:
		params = {'prefix': 'account:'}
		if cursor:
			params['cursor'] = cursor
		r = client.get(f'{kv_base}/keys', headers=headers, params=params)
		if r.status_code != 200:
			break
		data = r.json()
		keys.extend(k['name'] for k in data.get('result', []))
		info = data.get('result_info', {})
		if info.get('cursor') and data.get('result'):
			cursor = info['cursor']
		else:
			break
	return keys


def _kv_get(client: httpx.Client, kv_base: str, headers: dict, key: str) -> dict | None:
	r = client.get(f'{kv_base}/values/{key}', headers=headers)
	if r.status_code == 200:
		try:
			return r.json()
		except Exception:
			return None
	return None


OIDC_URL = 'https://oidc.{region}.amazonaws.com/token'


def _refresh_oidc(client: httpx.Client, account: dict) -> dict:
	rt = account.get('refresh_token', '')
	cid = account.get('client_id', '')
	cs = account.get('client_secret', '')
	region = account.get('region', 'us-east-1')

	if not rt or not cid or not cs:
		return {'success': False, 'error': 'Missing credentials'}

	url = OIDC_URL.replace('{region}', region)
	try:
		r = client.post(url, json={
			'clientId': cid, 'clientSecret': cs,
			'refreshToken': rt, 'grantType': 'refresh_token',
		}, timeout=30)
		if r.status_code == 200:
			data = r.json()
			return {
				'success': True,
				'accessToken': data.get('accessToken'),
				'refreshToken': data.get('refreshToken', rt),
			}
		return {'success': False, 'error': f'HTTP {r.status_code}'}
	except Exception as e:
		return {'success': False, 'error': str(e)[:100]}
