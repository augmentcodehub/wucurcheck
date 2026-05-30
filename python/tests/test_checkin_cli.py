"""Tests for wucur checkin command."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from typer.testing import CliRunner
from cli.app import app
from core.result import Result

runner = CliRunner()


class TestCheckin:
	def test_no_args_exits_1(self, tmp_path):
		output = tmp_path / 'out.json'
		result = runner.invoke(app, ['checkin', '--output', str(output)])
		assert result.exit_code == 1
		assert '--file' in result.output or '--username' in result.output

	def test_file_not_found(self, tmp_path):
		result = runner.invoke(app, ['checkin', '--file', '/nonexistent.json', '--output', str(tmp_path / 'o.json')])
		assert result.exit_code == 1
		assert 'not found' in result.output

	@patch('cli.checkin_cmd.CheckinPipeline')
	@patch('cli.checkin_cmd.time.sleep')
	def test_batch_checkin(self, mock_sleep, mock_pipeline_cls, tmp_path):
		accounts_file = tmp_path / 'accounts.json'
		accounts_file.write_text(json.dumps([
			{'username': 'a@qq.com', 'password': 'p1'},
			{'username': 'b@qq.com', 'password': 'p2'},
		]))
		output = tmp_path / 'results.json'

		mock_pipeline = MagicMock()
		mock_pipeline.execute.side_effect = [
			Result.ok({'balance': '9.24', 'checkin_message': '签到成功 +$0.88'}, message='签到成功 +$0.88'),
			Result.ok({'balance': '5.00', 'checkin_message': '今日已签到'}, message='今日已签到'),
		]
		mock_pipeline_cls.return_value = mock_pipeline

		result = runner.invoke(app, ['checkin', '--file', str(accounts_file), '--output', str(output)])
		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert len(data) == 2
		assert data[0]['username'] == 'a@qq.com'
		assert data[0]['status'] == 'active'
		assert data[0]['balance'] == '9.24'
		assert data[1]['last_result'] == '今日已签到'

	@patch('cli.checkin_cmd.CheckinPipeline')
	def test_single_checkin(self, mock_pipeline_cls, tmp_path):
		output = tmp_path / 'results.json'
		mock_pipeline = MagicMock()
		mock_pipeline.execute.return_value = Result.ok({'balance': '3.50'}, message='签到成功')
		mock_pipeline_cls.return_value = mock_pipeline

		result = runner.invoke(app, ['checkin', '--username', 'x@qq.com', '--password', 'pw', '--output', str(output)])
		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert len(data) == 1
		assert data[0]['username'] == 'x@qq.com'
		assert data[0]['balance'] == '3.50'

	@patch('cli.checkin_cmd.CheckinPipeline')
	def test_checkin_failure_keeps_active(self, mock_pipeline_cls, tmp_path):
		output = tmp_path / 'results.json'
		mock_pipeline = MagicMock()
		mock_pipeline.execute.return_value = Result.fail('登录失败: HTTP 429')
		mock_pipeline_cls.return_value = mock_pipeline

		result = runner.invoke(app, ['checkin', '--username', 'y@qq.com', '--password', 'pw', '--output', str(output)])
		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert data[0]['status'] == 'active'
		assert '登录失败' in data[0]['last_result']
