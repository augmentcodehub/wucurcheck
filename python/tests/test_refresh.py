"""Tests for wucur refresh command."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from typer.testing import CliRunner
from cli.app import app

runner = CliRunner()

ENV = {'CF_ACCOUNT_ID': 'acc123', 'CF_API_TOKEN': 'tok456', 'KV_NAMESPACE_ID': 'ns789'}


class TestRefresh:
	def test_missing_env_vars(self, tmp_path):
		output = tmp_path / 'out.json'
		with patch.dict('os.environ', {'CF_ACCOUNT_ID': '', 'CF_API_TOKEN': '', 'KV_NAMESPACE_ID': ''}, clear=False):
			result = runner.invoke(app, ['refresh', '--target', 'x@ouraihub.com', '--output', str(output)])
		assert result.exit_code == 1
		assert 'CF_ACCOUNT_ID' in result.output

	def test_no_target_or_all(self, tmp_path):
		output = tmp_path / 'out.json'
		with patch.dict('os.environ', ENV, clear=False):
			result = runner.invoke(app, ['refresh', '--output', str(output)])
		assert result.exit_code == 1
		assert '--target' in result.output or '--all' in result.output

	@patch('cli.refresh.httpx.Client')
	def test_refresh_single_success(self, mock_client_cls, tmp_path):
		output = tmp_path / 'out.json'
		mock_client = MagicMock()
		mock_client.__enter__ = MagicMock(return_value=mock_client)
		mock_client.__exit__ = MagicMock(return_value=False)

		# KV get returns a kiro account
		kv_resp = MagicMock()
		kv_resp.status_code = 200
		kv_resp.json.return_value = {
			'username': 'test@ouraihub.com',
			'platform': 'kiro',
			'refresh_token': 'rt_old',
			'client_id': 'cid',
			'client_secret': 'cs',
			'region': 'us-east-1',
		}

		# OIDC refresh returns new tokens
		oidc_resp = MagicMock()
		oidc_resp.status_code = 200
		oidc_resp.json.return_value = {'accessToken': 'at_new', 'refreshToken': 'rt_new'}

		mock_client.get.return_value = kv_resp
		mock_client.post.return_value = oidc_resp
		mock_client_cls.return_value = mock_client

		with patch.dict('os.environ', ENV, clear=False):
			result = runner.invoke(app, ['refresh', '--target', 'test@ouraihub.com', '--output', str(output)])

		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert len(data) == 1
		assert data[0]['username'] == 'test@ouraihub.com'
		assert data[0]['status'] == 'active'
		assert data[0]['accessToken'] == 'at_new'
		assert '成功' in data[0]['last_result']

	@patch('cli.refresh.httpx.Client')
	def test_refresh_oidc_failure(self, mock_client_cls, tmp_path):
		output = tmp_path / 'out.json'
		mock_client = MagicMock()
		mock_client.__enter__ = MagicMock(return_value=mock_client)
		mock_client.__exit__ = MagicMock(return_value=False)

		kv_resp = MagicMock()
		kv_resp.status_code = 200
		kv_resp.json.return_value = {
			'username': 'fail@ouraihub.com',
			'platform': 'kiro',
			'refresh_token': 'rt',
			'client_id': 'cid',
			'client_secret': 'cs',
		}

		oidc_resp = MagicMock()
		oidc_resp.status_code = 401
		oidc_resp.json.return_value = {}

		mock_client.get.return_value = kv_resp
		mock_client.post.return_value = oidc_resp
		mock_client_cls.return_value = mock_client

		with patch.dict('os.environ', ENV, clear=False):
			result = runner.invoke(app, ['refresh', '--target', 'fail@ouraihub.com', '--output', str(output)])

		assert result.exit_code == 0
		data = json.loads(output.read_text())
		assert data[0]['status'] == 'active'
		assert '刷新失败' in data[0]['last_result']
