"""Unified CLI entry point using Typer."""
import typer

from cli.callback import callback as callback_cmd

app = typer.Typer(name='wucur', no_args_is_help=True)
app.command('callback')(callback_cmd)


@app.command('version', hidden=True)
def version():
	"""Print version."""
	typer.echo('0.1.0')


def main():
	app()
