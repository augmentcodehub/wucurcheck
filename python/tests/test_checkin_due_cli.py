from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cli.checkin_due_cli import main


def test_help_shows_summary(capsys):
	try:
		main(['--help'])
	except SystemExit as exc:
		assert exc.code == 0
	else:
		raise AssertionError('expected SystemExit')
	output = capsys.readouterr().out
	assert 'Run the Wucur checkin-due service.' in output
	assert '--backend' in output
	assert '--dry-run' in output


def test_main_constructs_repository_and_service():
	fake_summary = MagicMock()
	fake_summary.scanned = 2
	fake_summary.due = 1
	fake_summary.skipped = 1
	fake_summary.succeeded = 1
	fake_summary.failed = 0
	fake_summary.exit_code = 0
	fake_summary.error_code = None
	fake_repository = MagicMock()
	fake_repository.__enter__.return_value = fake_repository
	fake_repository.__exit__.return_value = None
	provider = MagicMock(name='provider')

	with (
		patch('cli.checkin_due_cli._load_wucur_provider', return_value=provider),
		patch('cli.checkin_due_cli.build_backend_repository', return_value=fake_repository) as mock_build,
		patch('cli.checkin_due_cli.CheckinDueService', return_value=fake_repository) as mock_service,
		patch('cli.checkin_due_cli.CheckDueAccountsUseCase') as mock_use_case_cls,
	):
		mock_use_case = MagicMock()
		mock_use_case.run.return_value = fake_summary
		mock_use_case_cls.return_value = mock_use_case

		exit_code = main(['--backend', 'sqlite', '--db', 'demo.sqlite3', '--dry-run'])

	assert exit_code == 0
	mock_build.assert_called_once_with('sqlite', db_path='demo.sqlite3', worker_url=None, worker_token=None)
	mock_service.assert_called_once_with(fake_repository, provider)
	mock_use_case_cls.assert_called_once_with(fake_repository)
	mock_use_case.run.assert_called_once_with(
		as_of=None,
		timezone='Asia/Shanghai',
		dry_run=True,
		provider_scope='wucur',
	)
