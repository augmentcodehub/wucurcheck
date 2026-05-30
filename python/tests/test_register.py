"""Tests for wucur register command."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from typer.testing import CliRunner
from cli.app import app
from core.result import Result

runner = CliRunner()


class TestRegisterWucur:
	@patch('providers.wucur.WucurProvider.register')
	def test_register_wucur_success(self, mock_register, tmp_path):
		output = tmp_path / 'reg.json'
		mock_register.return_value = Result.ok({'success': True})

		result = runner.invoke(app, ['register', '--provider', 'wucur', '--count', '1', '--output', str(output)])
		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert len(data) == 1
		assert data[0]['status'] == 'active'
		assert data[0]['platform'] == 'wucur'
		assert data[0]['last_result'] == '注册成功'
		assert '@qq.com' in data[0]['username']

	@patch('providers.wucur.WucurProvider.register')
	def test_register_wucur_failure(self, mock_register, tmp_path):
		output = tmp_path / 'reg.json'
		mock_register.return_value = Result.fail('用户已存在')

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
		"""When EMAIL_API_KEY is missing, result is written with error message."""
		output = tmp_path / 'reg.json'
		with patch.dict('os.environ', {'EMAIL_API_KEY': ''}, clear=False):
			result = runner.invoke(app, ['register', '--provider', 'kiro', '--output', str(output)])
		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert '注册失败' in data[0]['last_result']

	@patch('providers.kiro.subprocess.run')
	def test_kiro_success(self, mock_run, tmp_path):
		output = tmp_path / 'reg.json'
		node_results = [{'status': 'success', 'email': 'test@ouraihub.com', 'password': 'pass123'}]
		tmp_node_output = Path('/tmp/kiro_register_output.json')
		tmp_node_output.write_text(json.dumps(node_results))

		mock_run.return_value = MagicMock(returncode=0, stderr='')

		with patch.dict('os.environ', {'EMAIL_API_KEY': 'key123'}, clear=False):
			with patch('providers.kiro._NODE_REGISTER_DIR', tmp_path):
				(tmp_path / 'dist').mkdir()
				(tmp_path / 'dist' / 'index.js').write_text('')
				result = runner.invoke(app, ['register', '--provider', 'kiro', '--count', '1', '--output', str(output)])

		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert len(data) == 1
		assert data[0]['username'] == 'test@ouraihub.com'
		assert data[0]['platform'] == 'kiro'
		assert data[0]['status'] == 'active'
