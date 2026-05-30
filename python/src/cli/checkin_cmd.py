"""wucur checkin — batch or single account checkin via CheckinPipeline."""
import json
import random
import time
from pathlib import Path
from typing import Optional

import typer

from core.result_record import ResultRecord
from pipelines.checkin import CheckinPipeline
from utils.logger import get_logger

log = get_logger('cli.checkin_cmd')


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

	log.info('Checkin start', count=len(accounts))
	pipeline = CheckinPipeline()
	results = _run_batch(pipeline, accounts)

	output.parent.mkdir(parents=True, exist_ok=True)
	output.write_text(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2), encoding='utf-8')
	log.info('Checkin done', count=len(results))
	typer.echo(f'Checkin done: {len(results)} account(s) → {output}')


def _run_batch(pipeline: CheckinPipeline, accounts: list[dict]) -> list[ResultRecord]:
	"""Execute checkin for each account with rate limiting."""
	results: list[ResultRecord] = []
	for i, acct in enumerate(accounts):
		uname = acct.get('username', '')
		pwd = acct.get('password', '')
		record = _checkin_one(pipeline, uname, pwd)
		results.append(record)

		if i < len(accounts) - 1:
			time.sleep(random.randint(15, 30) if (i + 1) % 15 != 0 else 120)

	return results


def _checkin_one(pipeline: CheckinPipeline, username: str, password: str) -> ResultRecord:
	"""Single account checkin — returns ResultRecord, never raises."""
	try:
		result = pipeline.execute(username, password)
	except Exception as e:
		log.error('Checkin exception', username=username, error=str(e)[:100])
		return ResultRecord(username=username, last_result=f'异常: {str(e)[:80]}')

	if result.success:
		log.info('Checkin success', username=username, result_msg=result.message)
	else:
		log.warning('Checkin failed', username=username, reason=result.message)

	return ResultRecord(
		username=username,
		last_result=result.message or ('签到成功' if result.success else '签到失败'),
		balance=result.data.get('balance') if result.data else None,
		checkin_time=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) if result.success else None,
	)
