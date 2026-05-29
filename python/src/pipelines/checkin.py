"""单账号签到 Pipeline：login → checkin → get_balance。"""
import httpx

from core.result import Result
from providers import get_provider
from utils.logger import get_logger

log = get_logger("pipeline.checkin")


class CheckinPipeline:
    """执行单账号签到流程。"""

    def execute(self, username: str, password: str, provider_name: str = "wucur") -> Result:
        provider = get_provider(provider_name)
        if not provider:
            return Result.fail(f"未知 provider: {provider_name}")

        with httpx.Client(http2=True, timeout=30.0) as client:
            # 1. Login
            login_result = provider.login(client, username, password)
            if not login_result.success:
                return Result.fail(f"登录失败: {login_result.message}")

            # 2. Build auth headers
            user_id = login_result.data.get("user_id", "") if login_result.data else ""
            headers = provider.build_auth_headers(user_id)

            # 3. Checkin
            checkin_result = provider.checkin(client, headers)
            log.info("Checkin done", extra={"username": username, "result_msg": checkin_result.message})

            # 4. Get balance
            balance_result = provider.get_balance(client, headers)
            balance = str(balance_result.data.get("quota", 0)) if balance_result.success and balance_result.data else None

        return Result.ok({
            "checkin_message": checkin_result.message,
            "balance": balance,
        }, message=checkin_result.message)
