"""Unified CLI entry point using Typer."""
import typer

from cli.callback import callback as callback_cmd
from cli.register import register as register_cmd
from cli.checkin_cmd import checkin as checkin_cmd

app = typer.Typer(name='wucur', no_args_is_help=True)
app.command('callback')(callback_cmd)
app.command('register')(register_cmd)
app.command('checkin')(checkin_cmd)


def main():
	app()
