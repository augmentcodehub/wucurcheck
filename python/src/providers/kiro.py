"""Kiro provider — register via node-register subprocess."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from core.result import Result
from providers._registry import provider_registry
from utils.logger import get_logger

log = get_logger('provider.kiro')

_NODE_REGISTER_DIR = Path(os.environ.get('NODE_REGISTER_DIR', str(Path(__file__).resolve().parents[2] / 'node-register')))


@provider_registry.register
class KiroProvider:
	name = 'kiro'
	domain = ''

	def register(self, username: str, password: str, *, email_domain: str = 'ouraihub.com', count: int = 1) -> Result:
		"""Register via node-register subprocess. username/password ignored (node generates them)."""
		email_api_key = os.environ.get('EMAIL_API_KEY', '')
		if not email_api_key:
			return Result.fail('EMAIL_API_KEY not set')

		dist = _NODE_REGISTER_DIR / 'dist' / 'index.js'
		if not dist.exists():
			return Result.fail(f'node-register not built: {dist}')

		tmp_output = Path('/tmp/kiro_register_output.json')
		cmd = [
			'node', str(dist),
			'--email-api-key', email_api_key,
			'--email-domain', email_domain,
			'--count', str(count),
			'--output', str(tmp_output),
		]

		log.info('Subprocess start', extra={'cmd': 'node dist/index.js', 'count': count})
		try:
			proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
		except subprocess.TimeoutExpired:
			log.error('Subprocess timeout', extra={'timeout_sec': 300})
			return Result.fail('Node 注册超时')

		if not tmp_output.exists():
			log.error('No output file', extra={'stderr': proc.stderr[:200]})
			return Result.fail(f'Node 注册失败: {proc.stderr[:200]}')

		node_results = json.loads(tmp_output.read_text(encoding='utf-8'))
		log.info('Subprocess done', extra={'result_count': len(node_results)})
		return Result.ok({'node_results': node_results})

	def login(self, client, username: str, password: str) -> Result:
		return Result.fail('Kiro does not support login')

	def checkin(self, client, headers: dict) -> Result:
		return Result.fail('Kiro does not support checkin')

	def get_balance(self, client, headers: dict) -> Result:
		return Result.fail('Kiro does not support get_balance')

	def build_auth_headers(self, user_id: str) -> dict:
		return {}
