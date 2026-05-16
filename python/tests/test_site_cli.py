from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cli.site_cli import main
from core.domain import StoredAccountRecord


@dataclass
class DummyResult:
	success: bool = True
	register: dict | None = None
	login: dict | None = None
	checkin: dict | None = None
	user_info: dict | None = None
	user_info_after_checkin: dict | None = None
	message: str | None = None


def test_site_cli_rejects_unknown_command(capsys):
	exit_code = main(['unknown'])

	assert exit_code == 2


def test_site_cli_supports_help(capsys):
	exit_code = main(['-h'])

	assert exit_code == 0


def test_site_cli_register_calls_use_case():
	fake_client = object()
	client_instance = MagicMock()
	client_instance.__enter__.return_value = fake_client
	client_instance.__exit__.return_value = None
	result = DummyResult(
		register={'success': True},
		login={'success': True},
		checkin={'success': True, 'data': {'quota_awarded': 100}},
		user_info={'success': True, 'quota': 1.0, 'used_quota': 0.5},
		user_info_after_checkin={'success': True, 'quota': 1.5, 'used_quota': 0.4},
	)

	with (
		patch('cli.site_cli.WucurCheckinClient', return_value=client_instance) as mock_client_cls,
		patch('cli.site_cli.RegisterAndCheckinAccountUseCase') as mock_use_case_cls,
	):
		mock_use_case = MagicMock()
		mock_use_case.run.return_value = result
		mock_use_case_cls.return_value = mock_use_case

		exit_code = main(
			[
				'register',
				'--name',
				'Console User',
				'--username',
				'alice@example.com',
				'--password',
				'secret',
			]
		)

	assert exit_code == 0
	mock_client_cls.assert_called_once()
	mock_use_case_cls.assert_called_once_with(fake_client)
	mock_use_case.run.assert_called_once()
	assert mock_use_case.run.call_args.kwargs['skip_checkin'] is False
	assert mock_use_case.run.call_args.kwargs['skip_balance'] is False


def test_site_cli_list_calls_use_case_and_renders_table():
	repository = MagicMock()
	repository.__enter__.return_value = repository
	repository.__exit__.return_value = None
	result = SimpleNamespace(
		records=[
			StoredAccountRecord(
				record_id='1',
				provider='wucur',
				name='Older',
				username='old@example.com',
				password='old-pass',
				registered_at='2026-05-14',
			),
			StoredAccountRecord(
				record_id='2',
				provider='wucur',
				name='Newer',
				username='new@example.com',
				password='new-pass',
				registered_at='2026-05-15',
			),
		]
	)

	with (
		patch('cli.site_cli.build_backend_repository', return_value=repository) as mock_build,
		patch('cli.site_cli.ListAccountsUseCase') as mock_use_case_cls,
		patch('scripts.query_wucur_accounts_db.print_table') as mock_print_table,
	):
		mock_use_case = MagicMock()
		mock_use_case.run.return_value = result
		mock_use_case_cls.return_value = mock_use_case

		exit_code = main(['list', '--db', 'demo.sqlite3', '--limit', '1'])

	assert exit_code == 0
	mock_build.assert_called_once_with('sqlite', db_path='demo.sqlite3', worker_url=None, worker_token=None)
	mock_use_case_cls.assert_called_once_with(repository)
	mock_use_case.run.assert_called_once_with(provider_scope='wucur')
	mock_print_table.assert_called_once()
	rendered_rows = mock_print_table.call_args.args[0]
	assert len(rendered_rows) == 1
	assert rendered_rows[0]['username'] == 'new@example.com'


def test_site_cli_checkin_calls_use_case():
	repository = MagicMock()
	repository.__enter__.return_value = repository
	repository.__exit__.return_value = None
	summary = SimpleNamespace(
		scanned=2,
		due=1,
		skipped=1,
		succeeded=1,
		failed=0,
		exit_code=0,
		error_code=None,
	)

	with (
		patch('cli.site_cli.build_backend_repository', return_value=repository) as mock_build,
		patch('cli.site_cli.CheckDueAccountsUseCase') as mock_use_case_cls,
	):
		mock_use_case = MagicMock()
		mock_use_case.run.return_value = summary
		mock_use_case_cls.return_value = mock_use_case

		exit_code = main(['checkin', '--backend', 'sqlite', '--db', 'demo.sqlite3', '--dry-run'])

	assert exit_code == 0
	mock_build.assert_called_once_with('sqlite', db_path='demo.sqlite3', worker_url=None, worker_token=None)
	mock_use_case_cls.assert_called_once()
	mock_use_case.run.assert_called_once_with(
		as_of=None,
		timezone='Asia/Shanghai',
		dry_run=True,
		provider_scope='wucur',
	)
