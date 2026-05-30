"""Tests for wucur register command."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from typer.testing import CliRunner
from cli.app import app

runner = CliRunner()


class TestRegisterWucur:
	@patch('cli.register.httpx.Client')
	def test_register_wucur_success(self, mock_client_cls, tmp_path):
		output = tmp_path / 'reg.json'
		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.json.return_value = {'success': True, 'message': 'ok'}
		mock_client = MagicMock()
		mock_client.__enter__ = MagicMock(return_value=mock_client)
		mock_client.__exit__ = MagicMock(return_value=False)
		mock_client.post.return_value = mock_resp
		mock_client_cls.return_value = mock_client

		result = runner.invoke(app, ['register', '--provider', 'wucur', '--count', '1', '--output', str(output)])
		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert len(data) == 1
		assert data[0]['status'] == 'active'
		assert data[0]['platform'] == 'wucur'
		assert data[0]['last_result'] == '注册成功'
		assert '@qq.com' in data[0]['username']

	@patch('cli.register.httpx.Client')
	def test_register_wucur_failure(self, mock_client_cls, tmp_path):
		output = tmp_path / 'reg.json'
		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.json.return_value = {'success': False, 'message': '用户已存在'}
		mock_client = MagicMock()
		mock_client.__enter__ = MagicMock(return_value=mock_client)
		mock_client.__exit__ = MagicMock(return_value=False)
		mock_client.post.return_value = mock_resp
		mock_client_cls.return_value = mock_client

		result = runner.invoke(app, ['register', '--provider', 'wucur', '--count', '1', '--output', str(output)])
		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert '注册失败' in data[0]['last_result']
		assert data[0]['status'] == 'active'

	def test_unknown_provider(self, tmp_path):
		output = tmp_path / 'reg.json'
		result = runner.invoke(app, ['register', '--provider', 'unknown', '--output', str(output)])
		assert result.exit_code == 1


class TestRegisterKiro:
	def test_kiro_missing_email_api_key(self, tmp_path):
		output = tmp_path / 'reg.json'
		with patch.dict('os.environ', {'EMAIL_API_KEY': ''}, clear=False):
			result = runner.invoke(app, ['register', '--provider', 'kiro', '--output', str(output)])
		assert result.exit_code == 1
		assert 'EMAIL_API_KEY' in result.output

	@patch('cli.register.subprocess.run')
	def test_kiro_success(self, mock_run, tmp_path):
		output = tmp_path / 'reg.json'
		node_results = [{'status': 'success', 'email': 'test@ouraihub.com', 'password': 'pass123'}]
		tmp_node_output = Path('/tmp/kiro_register_output.json')
		tmp_node_output.write_text(json.dumps(node_results))

		mock_run.return_value = MagicMock(returncode=0, stderr='')

		with patch.dict('os.environ', {'EMAIL_API_KEY': 'key123'}, clear=False):
			result = runner.invoke(app, ['register', '--provider', 'kiro', '--count', '1', '--output', str(output)])

		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert len(data) == 1
		assert data[0]['username'] == 'test@ouraihub.com'
		assert data[0]['platform'] == 'kiro'
		assert data[0]['status'] == 'active'
