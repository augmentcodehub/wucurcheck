"""Unit tests for checkin_batch core functions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scripts.checkin_batch import format_balance, format_quota_awarded, build_checkin_result, build_already_checked_result


class TestFormatBalance:
    """get_user_info returns quota already in dollar float format."""

    def test_normal_balance(self):
        assert format_balance({"success": True, "quota": 9.24}) == "9.24"

    def test_zero_balance(self):
        assert format_balance({"success": True, "quota": 0}) == "0"

    def test_missing_quota_defaults_zero(self):
        assert format_balance({"success": True}) == "0"

    def test_does_not_divide_by_500000(self):
        """Regression: get_user_info already converts, must NOT divide again."""
        result = format_balance({"success": True, "quota": 9.24})
        assert result == "9.24"
        assert float(result) > 1  # if divided again would be ~0.00


class TestFormatQuotaAwarded:
    """quota_awarded from checkin API is raw integer, needs /500000."""

    def test_one_dollar(self):
        assert format_quota_awarded(500000) == "+$1.00"

    def test_half_dollar(self):
        assert format_quota_awarded(250000) == "+$0.50"

    def test_real_value(self):
        assert format_quota_awarded(647767) == "+$1.30"

    def test_zero(self):
        assert format_quota_awarded(0) == "+$0.00"


class TestBuildCheckinResult:
    def test_success_with_balance(self):
        checkin_resp = {"data": {"quota_awarded": 500000, "checkin_date": "2026-05-27"}}
        info = {"success": True, "quota": 9.24}

        result = build_checkin_result("test@qq.com", checkin_resp, info)

        assert result["username"] == "test@qq.com"
        assert result["status"] == "active"
        assert "+$1.00" in result["last_result"]
        assert result["checkin_time"] == "2026-05-27"
        assert result["balance"] == "9.24"

    def test_success_without_info(self):
        checkin_resp = {"data": {"quota_awarded": 300000, "checkin_date": "2026-05-27"}}

        result = build_checkin_result("test@qq.com", checkin_resp, None)

        assert result["status"] == "active"
        assert "balance" not in result

    def test_info_request_failed(self):
        checkin_resp = {"data": {"quota_awarded": 300000, "checkin_date": "2026-05-27"}}
        info = {"success": False, "error": "timeout"}

        result = build_checkin_result("test@qq.com", checkin_resp, info)

        assert "balance" not in result
        assert result["status"] == "active"


class TestBuildAlreadyCheckedResult:
    def test_with_balance(self):
        info = {"success": True, "quota": 11.11}

        result = build_already_checked_result("test@qq.com", info)

        assert result["username"] == "test@qq.com"
        assert result["status"] == "active"
        assert result["last_result"] == "今日已签到"
        assert result["balance"] == "11.11"
        assert "T" in result["checkin_time"]

    def test_without_info(self):
        result = build_already_checked_result("test@qq.com", None)

        assert result["status"] == "active"
        assert "balance" not in result
        assert result["last_result"] == "今日已签到"
