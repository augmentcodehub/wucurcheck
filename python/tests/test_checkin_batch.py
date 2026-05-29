"""Unit tests for checkin pipeline and batch script."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.result import Result
from pipelines.checkin import CheckinPipeline
from lib.constants import QUOTA_UNIT_DIVISOR


class TestResult:
    def test_ok(self):
        r = Result.ok({"key": "val"}, message="done")
        assert r.success is True
        assert r.data == {"key": "val"}
        assert r.message == "done"

    def test_fail(self):
        r = Result.fail("error msg")
        assert r.success is False
        assert r.message == "error msg"


class TestCheckinPipeline:
    def test_unknown_provider(self):
        pipeline = CheckinPipeline()
        result = pipeline.execute("user@test.com", "pass", provider_name="nonexistent")
        assert result.success is False
        assert "未知 provider" in result.message

    @patch("pipelines.checkin.get_provider")
    def test_login_failure(self, mock_get_provider):
        provider = MagicMock()
        provider.login.return_value = Result.fail("Invalid parameters")
        mock_get_provider.return_value = provider

        pipeline = CheckinPipeline()
        result = pipeline.execute("user@test.com", "")
        assert result.success is False
        assert "登录失败" in result.message

    @patch("pipelines.checkin.get_provider")
    def test_checkin_success(self, mock_get_provider):
        provider = MagicMock()
        provider.login.return_value = Result.ok({"user_id": "123"})
        provider.build_auth_headers.return_value = {"User-Agent": "test"}
        provider.checkin.return_value = Result.ok({"data": {}}, message="签到成功 +$1.00")
        provider.get_balance.return_value = Result.ok({"quota": 9.24, "used": 1.0})
        mock_get_provider.return_value = provider

        pipeline = CheckinPipeline()
        result = pipeline.execute("user@test.com", "pass123")
        assert result.success is True
        assert result.message == "签到成功 +$1.00"
        assert result.data["balance"] == "9.24"

    @patch("pipelines.checkin.get_provider")
    def test_already_checked_in(self, mock_get_provider):
        provider = MagicMock()
        provider.login.return_value = Result.ok({"user_id": "123"})
        provider.build_auth_headers.return_value = {}
        provider.checkin.return_value = Result.ok({}, message="今日已签到")
        provider.get_balance.return_value = Result.ok({"quota": 8.42, "used": 0.5})
        mock_get_provider.return_value = provider

        pipeline = CheckinPipeline()
        result = pipeline.execute("user@test.com", "pass123")
        assert result.success is True
        assert result.message == "今日已签到"
        assert result.data["balance"] == "8.42"


class TestQuotaDivisor:
    """Verify the constant is correct."""

    def test_value(self):
        assert QUOTA_UNIT_DIVISOR == 500_000

    def test_conversion(self):
        raw = 4621350
        dollar = round(raw / QUOTA_UNIT_DIVISOR, 2)
        assert dollar == 9.24
