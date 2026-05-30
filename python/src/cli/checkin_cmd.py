"""wucur checkin — batch or single account checkin via CheckinPipeline."""
import json
import random
import time
from pathlib import Path
from typing import Optional

import typer

from pipelines.checkin import CheckinPipeline


def checkin(
	file: Optional[Path] = typer.Option(None, '--file', help='JSON file with accounts [{username, password}]'),
	username: Optional[str] = typer.Option(None, '--username', help='Single account username'),
	password: Optional[str] = typer.Option(None, '--password', help='Single account password'),
	output: Path = typer.Option('results.json', '--output', help='Output results.json path'),
):
	"""Checkin accounts (batch from file or single)."""
	if file:
		if not file.exists():
			typer.echo(f'Error: {file} not found', err=True)
			raise typer.Exit(1)
		accounts = json.loads(file.read_text(encoding='utf-8'))
	elif username:
		accounts = [{'username': username, 'password': password or ''}]
	else:
		typer.echo('Error: provide --file or --username', err=True)
		raise typer.Exit(1)

	pipeline = CheckinPipeline()
	results = []

	for i, acct in enumerate(accounts):
		uname = acct.get('username', '')
		pwd = acct.get('password', '')
		try:
			result = pipeline.execute(uname, pwd)
			results.append({
				'username': uname,
				'status': 'active',
				'last_result': result.message or ('签到成功' if result.success else '签到失败'),
				'balance': result.data.get('balance') if result.data else None,
				'checkin_time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) if result.success else None,
			})
		except Exception as e:
			results.append({'username': uname, 'status': 'active', 'last_result': f'异常: {str(e)[:80]}'})

		if i < len(accounts) - 1:
			time.sleep(random.randint(15, 30) if (i + 1) % 15 != 0 else 120)

	output.parent.mkdir(parents=True, exist_ok=True)
	output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
	typer.echo(f'Checkin done: {len(results)} account(s) → {output}')
