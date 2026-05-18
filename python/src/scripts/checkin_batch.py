"""Batch checkin: read accounts from JSON, checkin one by one with delay."""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.http.wucur_client import login_account, checkin_account, get_user_info
from core.provider_profile import ProviderProfileResolver
from utils.logger import get_logger
import httpx

log = get_logger("scripts.checkin_batch")

ACCOUNTS_FILE = Path("artifacts/checkin_accounts.json")
RESULTS_FILE = Path("artifacts/checkin_results.json")


def run():
    if not ACCOUNTS_FILE.exists():
        log.error("No accounts file found", extra={"path": str(ACCOUNTS_FILE)})
        return

    accounts = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    log.info("Batch checkin started", extra={"count": len(accounts)})

    resolver = ProviderProfileResolver()
    profile = resolver.resolve("wucur")
    domain = profile.domain
    sign_in_url = f"{domain}{profile.sign_in_path}"
    user_info_url = f"{domain}{profile.user_info_path}"

    results = []

    for i, acct in enumerate(accounts):
        username = acct.get("username", "")
        password = acct.get("password", "")

        result = {"username": username, "status": "failed", "last_result": "签到失败"}

        with httpx.Client(http2=True, timeout=30.0) as client:
            try:
                login_resp = login_account(client, username, password)
                if not login_resp.get("success"):
                    result["last_result"] = f"登录失败: {login_resp.get('message', '')}"
                    log.warning("Login failed", extra={"username": username, "reason": login_resp.get("message")})
                    results.append(result)
                    continue

                user_id = str(login_resp.get("data", {}).get("id", ""))
                headers = {}
                if profile.api_user_key and user_id:
                    headers[profile.api_user_key] = user_id

                checkin_resp = checkin_account(client, headers, sign_in_url)
                if checkin_resp.get("success"):
                    quota = checkin_resp.get("data", {}).get("quota_awarded", 0)
                    result["status"] = "active"
                    result["last_result"] = f"签到成功 +${quota/500000:.2f}"
                    result["checkin_time"] = checkin_resp.get("data", {}).get("checkin_date", "")

                    info = get_user_info(client, headers, user_info_url)
                    if info.get("success"):
                        result["balance"] = str(info.get("quota", 0))

                    log.info("Checkin success", extra={"username": username, "quota": quota})
                else:
                    msg = checkin_resp.get('message', '')
                    if '已签到' in msg or '已经签到' in msg or 'already' in msg.lower():
                        result["status"] = "active"
                        result["last_result"] = "今日已签到"
                        log.info("Already checked in", extra={"username": username})
                    else:
                        result["last_result"] = f"签到失败: {msg}"
                        log.warning("Checkin failed", extra={"username": username, "reason": msg})

            except Exception as e:
                result["last_result"] = f"异常: {str(e)[:100]}"
                log.error("Checkin exception", extra={"username": username, "error": str(e)[:100]})

        results.append(result)

        if i < len(accounts) - 1:
            delay = random.randint(5, 10)
            time.sleep(delay)

    RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    success = sum(1 for r in results if r["status"] == "active")
    log.info("Batch checkin completed", extra={"success": success, "total": len(results)})


if __name__ == "__main__":
    run()
