"""wucur callback — read results.json and POST to Worker /callback."""
import json
import os
from pathlib import Path

import httpx
import typer


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

	with httpx.Client(timeout=30) as client:
		resp = client.post(url, json=payload)
		typer.echo(resp.text)
		if resp.status_code != 200:
			raise typer.Exit(1)
