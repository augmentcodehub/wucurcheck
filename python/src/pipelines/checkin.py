"""单账号签到 Pipeline：login → get_balance → checkin → get_balance → 比较。"""
import httpx

from core.result import Result
from providers import get_provider
from utils.logger import get_logger

log = get_logger("pipeline.checkin")


class CheckinPipeline:
    """执行单账号签到流程。通过余额变化判断是否真正签到成功。"""

    def execute(self, username: str, password: str, provider_name: str = "wucur") -> Result:
        provider = get_provider(provider_name)
        if not provider:
            return Result.fail(f"未知 provider: {provider_name}")

        try:
            with httpx.Client(http2=True, timeout=30.0) as client:
                # 1. Login
                login_result = provider.login(client, username, password)
                if not login_result.success:
                    return Result.fail(f"登录失败: {login_result.message}")

                # 2. Build auth headers
                user_id = login_result.data.get("user_id", "") if login_result.data else ""
                headers = provider.build_auth_headers(user_id)

                # 3. Get balance BEFORE checkin
                before_result = provider.get_balance(client, headers)
                before_quota = before_result.data.get("quota", 0) if before_result.success and before_result.data else None

                # 4. Checkin
                checkin_result = provider.checkin(client, headers)
                log.info("Checkin done", extra={"username": username, "result_msg": checkin_result.message})

                # 5. Get balance AFTER checkin
                after_result = provider.get_balance(client, headers)
                after_quota = after_result.data.get("quota", 0) if after_result.success and after_result.data else None

                # 6. 判断余额是否增加
                balance_increased = (
                    before_quota is not None
                    and after_quota is not None
                    and after_quota > before_quota
                )

                log.info("Balance check", extra={
                    "username": username,
                    "before": str(before_quota),
                    "after": str(after_quota),
                    "increased": str(balance_increased),
                })

            return Result.ok({
                "checkin_message": checkin_result.message,
                "balance": str(after_quota) if after_quota is not None else None,
                "before_quota": before_quota,
                "after_quota": after_quota,
                "balance_increased": balance_increased,
            }, message=checkin_result.message)

        except httpx.TimeoutException:
            log.error("Request timeout", extra={"username": username, "provider": provider_name})
            return Result.fail("请求超时")
        except httpx.ConnectError as e:
            log.error("Connection failed", extra={"username": username, "error": str(e)[:100]})
            return Result.fail(f"连接失败: {str(e)[:50]}")
        except Exception as e:
            log.error("Unexpected error", extra={"username": username, "error": str(e)[:100]})
            return Result.fail(f"异常: {str(e)[:50]}")
