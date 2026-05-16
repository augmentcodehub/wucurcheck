"""Batch checkin: read accounts from JSON, checkin one by one with delay."""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.http.wucur_client import login_account, checkin_account, get_user_info
from core.provider_profile import ProviderProfileResolver
import httpx

ACCOUNTS_FILE = Path("artifacts/checkin_accounts.json")
RESULTS_FILE = Path("artifacts/checkin_results.json")


def run():
    if not ACCOUNTS_FILE.exists():
        print("[ERROR] No accounts file found")
        return

    accounts = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    print(f"[INFO] Loaded {len(accounts)} accounts to checkin")

    resolver = ProviderProfileResolver()
    profile = resolver.resolve("wucur")
    results = []

    with httpx.Client(http2=True, timeout=30.0) as client:
        for i, acct in enumerate(accounts):
            username = acct.get("username", "")
            password = acct.get("password", "")
            print(f"--- [{i+1}/{len(accounts)}] {username} ---")

            result = {"username": username, "status": "failed", "last_result": "签到失败"}

            try:
                # Login
                login_resp = login_account(client, username, password)
                if not login_resp.get("success"):
                    result["last_result"] = f"登录失败: {login_resp.get('message', '')}"
                    results.append(result)
                    continue

                token = login_resp.get("token") or login_resp.get("data", {}).get("token", "")
                headers = {"Authorization": f"Bearer {token}"} if token else {}

                # Checkin
                sign_in_url = profile.sign_in_url if profile else "http://wucur.com:6543/api/user/checkin"
                checkin_resp = checkin_account(client, headers, sign_in_url)
                if checkin_resp.get("success"):
                    quota = checkin_resp.get("data", {}).get("quota_awarded", 0)
                    result["status"] = "active"
                    result["last_result"] = f"签到成功 +{quota/500000:.2f}"
                    result["checkin_time"] = checkin_resp.get("data", {}).get("checkin_date", "")

                    # Get balance
                    user_info_url = profile.user_info_url if profile else "http://wucur.com:6543/api/user/self"
                    info = get_user_info(client, headers, user_info_url)
                    if info.get("success"):
                        result["balance"] = str(info.get("quota", 0))
                else:
                    result["last_result"] = f"签到失败: {checkin_resp.get('message', '')}"

            except Exception as e:
                result["last_result"] = f"异常: {str(e)[:100]}"

            results.append(result)
            print(f"  -> {result['last_result']}")

            # Random delay 5-10s
            if i < len(accounts) - 1:
                delay = random.randint(5, 10)
                print(f"  等待 {delay}s...")
                time.sleep(delay)

    RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    success = sum(1 for r in results if r["status"] == "active")
    print(f"\n[DONE] {success}/{len(results)} 签到成功")


if __name__ == "__main__":
    run()
