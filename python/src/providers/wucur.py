"""Wucur provider — login/checkin/get_balance 实现。

所有方法接收 httpx.Client 参数，由 Pipeline 管理 client 生命周期。
login 设置的 session cookie 会自动在后续 checkin/get_balance 中复用。
"""
import httpx

from providers._registry import provider_registry
from core.result import Result
from lib.http import build_headers, parse_response
from lib.constants import QUOTA_UNIT_DIVISOR, DEFAULT_USER_AGENT
from utils.logger import get_logger

log = get_logger("provider.wucur")


@provider_registry.register
class WucurProvider:
    name = "wucur"
    domain = "http://wucur.com:6543"
    login_path = "/login"
    login_api_path = "/api/user/login"
    checkin_path = "/api/user/checkin"
    user_info_path = "/api/user/self"
    api_user_key = "new-api-user"

    def login(self, client: httpx.Client, username: str, password: str) -> Result:
        """登录并设置 session cookie 到 client 上。"""
        headers = build_headers(self.domain, self.login_path)
        resp = client.post(
            f"{self.domain}{self.login_api_path}",
            headers=headers,
            json={"username": username, "password": password},
            timeout=30,
        )
        data = parse_response(resp)
        if resp.status_code != 200 or not data.get("success"):
            msg = data.get("message", f"HTTP {resp.status_code}")
            log.warning("Login failed", extra={"username": username, "reason": msg})
            return Result.fail(msg)
        if "session" not in client.cookies:
            log.warning("Login no session cookie", extra={"username": username})
            return Result.fail("Login succeeded but session cookie not found")
        user_id = str(data.get("data", {}).get("id", ""))
        log.info("Login success", extra={"username": username})
        return Result.ok({"user_id": user_id, "raw": data})

    def checkin(self, client: httpx.Client, headers: dict) -> Result:
        """执行签到。需要 login 后的 session cookie（已在 client 中）。"""
        checkin_headers = {**headers, "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"}
        resp = client.post(f"{self.domain}{self.checkin_path}", headers=checkin_headers, timeout=30)
        data = parse_response(resp)
        if not data.get("success"):
            msg = data.get("message", "")
            if "已签到" in msg or "已经签到" in msg:
                return Result.ok(data, message="今日已签到")
            log.warning("Checkin failed", extra={"status": resp.status_code, "msg": msg[:80]})
            return Result.fail(msg, data)
        quota_awarded = data.get("data", {}).get("quota_awarded", 0)
        return Result.ok(data, message=f"签到成功 +${quota_awarded / QUOTA_UNIT_DIVISOR:.2f}")

    def get_balance(self, client: httpx.Client, headers: dict) -> Result:
        """获取余额。需要 login 后的 session cookie。"""
        resp = client.get(f"{self.domain}{self.user_info_path}", headers=headers, timeout=30)
        data = parse_response(resp)
        if resp.status_code != 200 or not data.get("success"):
            log.warning("Get balance failed", extra={"status": resp.status_code})
            return Result.fail(f"HTTP {resp.status_code}")
        user = data.get("data", {})
        return Result.ok({
            "quota": round(user.get("quota", 0) / QUOTA_UNIT_DIVISOR, 2),
            "used": round(user.get("used_quota", 0) / QUOTA_UNIT_DIVISOR, 2),
        })

    def build_auth_headers(self, user_id: str) -> dict:
        """构建认证后的请求头。"""
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        }
        if self.api_user_key and user_id:
            headers[self.api_user_key] = user_id
        return headers
