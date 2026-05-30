"""Tests for wucur callback command."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

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

	@patch('cli.callback.httpx.Client')
	def test_success(self, mock_client_cls, tmp_path):
		f = tmp_path / 'results.json'
		data = [{'username': 'test@qq.com', 'status': 'active', 'last_result': '签到成功'}]
		f.write_text(json.dumps(data))

		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.text = '{"ok":true}'
		mock_client = MagicMock()
		mock_client.__enter__ = MagicMock(return_value=mock_client)
		mock_client.__exit__ = MagicMock(return_value=False)
		mock_client.post.return_value = mock_resp
		mock_client_cls.return_value = mock_client

		with patch.dict('os.environ', {'CALLBACK_URL': 'http://worker/callback', 'CALLBACK_SECRET': 'sec'}, clear=False):
			result = runner.invoke(app, ['callback', '--file', str(f)])

		assert result.exit_code == 0
		assert '{"ok":true}' in result.output
		mock_client.post.assert_called_once()
		call_args = mock_client.post.call_args
		payload = call_args[1]['json']
		assert payload['secret'] == 'sec'
		assert payload['action'] == 'batch_result'
		assert payload['data']['results'] == data

	@patch('cli.callback.httpx.Client')
	def test_non_200_exits_1(self, mock_client_cls, tmp_path):
		f = tmp_path / 'results.json'
		f.write_text('[{"username":"x@y.com","status":"active"}]')

		mock_resp = MagicMock()
		mock_resp.status_code = 500
		mock_resp.text = 'Internal Server Error'
		mock_client = MagicMock()
		mock_client.__enter__ = MagicMock(return_value=mock_client)
		mock_client.__exit__ = MagicMock(return_value=False)
		mock_client.post.return_value = mock_resp
		mock_client_cls.return_value = mock_client

		with patch.dict('os.environ', {'CALLBACK_URL': 'http://worker/callback', 'CALLBACK_SECRET': 's'}, clear=False):
			result = runner.invoke(app, ['callback', '--file', str(f)])

		assert result.exit_code == 1
