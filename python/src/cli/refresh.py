"""wucur refresh — refresh kiro OIDC tokens via Cloudflare KV."""
import json
import os
from pathlib import Path
from typing import Optional

import httpx
import typer

from core.result_record import ResultRecord
from utils.logger import get_logger

log = get_logger('cli.refresh')


# --- Service classes ---

class KvClient:
	"""Cloudflare KV read operations."""

	def __init__(self, client: httpx.Client, account_id: str, namespace_id: str, api_token: str):
		self._client = client
		self._base = f'https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}'
		self._headers = {'Authorization': f'Bearer {api_token}'}

	def list_keys(self, prefix: str = 'account:') -> list[str]:
		keys: list[str] = []
		cursor = None
		while True:
			params: dict = {'prefix': prefix}
			if cursor:
				params['cursor'] = cursor
			r = self._client.get(f'{self._base}/keys', headers=self._headers, params=params)
			if r.status_code != 200:
				log.warning('KV list failed', extra={'status': r.status_code})
				break
			data = r.json()
			keys.extend(k['name'] for k in data.get('result', []))
			info = data.get('result_info', {})
			cursor = info.get('cursor') if data.get('result') else None
			if not cursor:
				break
		return keys

	def get(self, key: str) -> dict | None:
		r = self._client.get(f'{self._base}/values/{key}', headers=self._headers)
		if r.status_code != 200:
			return None
		try:
			return r.json()
		except (json.JSONDecodeError, ValueError):
			log.warning('KV parse failed', extra={'key': key})
			return None


class OidcRefresher:
	"""AWS OIDC token refresh."""

	OIDC_URL = 'https://oidc.{region}.amazonaws.com/token'

	def __init__(self, client: httpx.Client):
		self._client = client

	def refresh(self, account: dict) -> dict:
		"""Returns {'success': bool, 'accessToken'?: str, 'refreshToken'?: str, 'error'?: str}."""
		rt = account.get('refresh_token', '')
		cid = account.get('client_id', '')
		cs = account.get('client_secret', '')
		region = account.get('region', 'us-east-1')

		if not rt or not cid or not cs:
			return {'success': False, 'error': 'Missing credentials'}

		url = self.OIDC_URL.replace('{region}', region)
		try:
			r = self._client.post(url, json={
				'clientId': cid, 'clientSecret': cs,
				'refreshToken': rt, 'grantType': 'refresh_token',
			}, timeout=30)
		except httpx.TimeoutException:
			return {'success': False, 'error': 'OIDC request timeout'}
		except httpx.ConnectError as e:
			return {'success': False, 'error': f'Connect error: {str(e)[:60]}'}

		if r.status_code == 200:
			data = r.json()
			return {
				'success': True,
				'accessToken': data.get('accessToken'),
				'refreshToken': data.get('refreshToken', rt),
			}
		return {'success': False, 'error': f'HTTP {r.status_code}'}


# --- CLI command ---

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

	log.info('Refresh start', extra={'target': target or 'all'})

	with httpx.Client(http2=True, timeout=30) as client:
		kv = KvClient(client, cf_account_id, kv_namespace_id, cf_api_token)
		oidc = OidcRefresher(client)

		keys = [f'account:{target}'] if target else kv.list_keys()
		results = _refresh_accounts(kv, oidc, keys)

	output.parent.mkdir(parents=True, exist_ok=True)
	output.write_text(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2), encoding='utf-8')
	log.info('Refresh done', extra={'count': len(results)})
	typer.echo(f'Refresh done: {len(results)} account(s) → {output}')


def _refresh_accounts(kv: KvClient, oidc: OidcRefresher, keys: list[str]) -> list[ResultRecord]:
	"""Pure logic: iterate keys, filter kiro accounts, refresh tokens."""
	results: list[ResultRecord] = []
	for key in keys:
		account = kv.get(key)
		if not account or account.get('platform') != 'kiro' or not account.get('refresh_token'):
			continue

		username = account.get('username', '')
		r = oidc.refresh(account)
		if r['success']:
			log.info('Refresh success', extra={'username': username})
			results.append(ResultRecord(
				username=username, last_result='Token 刷新成功',
				refreshToken=r['refreshToken'], accessToken=r['accessToken'],
			))
		else:
			log.warning('Refresh failed', extra={'username': username, 'error': r['error']})
			results.append(ResultRecord(username=username, last_result=f"刷新失败: {r['error']}"))

	return results
