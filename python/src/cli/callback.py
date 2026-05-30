"""wucur callback — read results.json and POST to Worker /callback."""
import json
import os
from pathlib import Path

import httpx
import typer

from utils.logger import get_logger

log = get_logger('cli.callback')


def callback(
	file: Path = typer.Option(..., '--file', help='Path to results.json'),
):
	"""Read results.json and POST to Worker callback endpoint."""
	url = os.environ.get('CALLBACK_URL', '')
	secret = os.environ.get('CALLBACK_SECRET', '')
	if not url:
		typer.echo('Error: CALLBACK_URL not set', err=True)
		raise typer.Exit(1)

	if not file.exists():
		typer.echo(f'Error: {file} not found', err=True)
		raise typer.Exit(1)

	results = json.loads(file.read_text(encoding='utf-8'))
	payload = {'secret': secret, 'action': 'batch_result', 'data': {'results': results}}
	log.info('Callback start', extra={'url': url, 'result_count': len(results)})

	try:
		with httpx.Client(timeout=30) as client:
			resp = client.post(url, json=payload)
	except httpx.TimeoutException:
		log.error('Callback timeout', extra={'url': url})
		typer.echo('Error: callback request timeout', err=True)
		raise typer.Exit(1)
	except httpx.ConnectError as e:
		log.error('Callback connect error', extra={'url': url, 'error': str(e)[:80]})
		typer.echo(f'Error: {e}', err=True)
		raise typer.Exit(1)

	typer.echo(resp.text)
	if resp.status_code != 200:
		log.warning('Callback non-200', extra={'status': resp.status_code})
		raise typer.Exit(1)
	log.info('Callback success', extra={'status': resp.status_code})
