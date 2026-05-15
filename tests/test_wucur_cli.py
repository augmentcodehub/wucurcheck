from pathlib import Path
from unittest.mock import patch

import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from wucur_cli.cli import main


def test_help_lists_commands(capsys):
	exit_code = main(['help'])

	assert exit_code == 0
	output = capsys.readouterr().out
	assert 'Wucur 命令总览' in output
	assert 'export' in output
	assert 'pipeline' in output


def test_help_for_specific_command(capsys):
	exit_code = main(['help', 'export'])

	assert exit_code == 0
	output = capsys.readouterr().out
	assert '命令: export' in output
	assert '导出 SQLite 为 JSON 和 CSV' in output


def test_command_is_forwarded():
	fake_module = type('FakeModule', (), {'main': staticmethod(lambda argv=None: 0)})()
	with patch('wucur_cli.cli.import_module', return_value=fake_module) as mock_import:
		exit_code = main(['export', '--stdout-json'])

	assert exit_code == 0
	mock_import.assert_called_once_with('scripts.export_wucur_accounts')
