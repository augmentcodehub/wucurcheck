"""Tests for wucur callback command."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from typer.testing import CliRunner
from cli.app import app

runner = CliRunner()


class TestCallback:
	def test_missing_callback_url(self, tmp_path):
		f = tmp_path / 'results.json'
		f.write_text('[{"username":"a@b.com","status":"active"}]')
		with patch.dict('os.environ', {'CALLBACK_URL': '', 'CALLBACK_SECRET': ''}, clear=False):
			result = runner.invoke(app, ['callback', '--file', str(f)])
		assert result.exit_code == 1
		assert 'CALLBACK_URL' in result.output

	def test_missing_file(self):
		with patch.dict('os.environ', {'CALLBACK_URL': 'http://x', 'CALLBACK_SECRET': 's'}, clear=False):
			result = runner.invoke(app, ['callback', '--file', '/nonexistent.json'])
		assert result.exit_code == 1
		assert 'not found' in result.output

	@patch('pycore.callback.post')
	def test_success(self, mock_post, tmp_path):
		f = tmp_path / 'results.json'
		data = [{'username': 'test@qq.com', 'status': 'active', 'last_result': '签到成功'}]
		f.write_text(json.dumps(data))

		mock_post.return_value = MagicMock(body='{"ok":true}', status=200)

		with patch.dict('os.environ', {'CALLBACK_URL': 'http://worker/callback', 'CALLBACK_SECRET': 'sec'}, clear=False):
			result = runner.invoke(app, ['callback', '--file', str(f)])

		assert result.exit_code == 0
		assert '{"ok":true}' in result.output
		mock_post.assert_called_once()
		call_args = mock_post.call_args
		payload = call_args[1]['json']
		assert payload['secret'] == 'sec'
		assert payload['action'] == 'batch_result'
		assert payload['data']['results'] == data

	@patch('pycore.callback.post')
	def test_http_error_exits_1(self, mock_post, tmp_path):
		from pycore.http import HttpError
		f = tmp_path / 'results.json'
		f.write_text('[{"username":"x@y.com","status":"active"}]')

		mock_post.side_effect = HttpError(500, 'Internal Server Error')

		with patch.dict('os.environ', {'CALLBACK_URL': 'http://worker/callback', 'CALLBACK_SECRET': 's'}, clear=False):
			result = runner.invoke(app, ['callback', '--file', str(f)])

		assert result.exit_code == 1
