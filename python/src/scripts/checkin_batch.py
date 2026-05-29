"""Batch checkin: read accounts from JSON, checkin one by one via Pipeline."""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.checkin import CheckinPipeline
from utils.logger import get_logger

log = get_logger("scripts.checkin_batch")

ACCOUNTS_FILE = Path("artifacts/checkin_accounts.json")
RESULTS_FILE = Path("artifacts/checkin_results.json")


def run():
    if not ACCOUNTS_FILE.exists():
        log.error("No accounts file found", extra={"path": str(ACCOUNTS_FILE)})
        return

    accounts = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    log.info("Batch checkin started", extra={"count": len(accounts)})

    pipeline = CheckinPipeline()
    results = []

    for i, acct in enumerate(accounts):
        username = acct.get("username", "")
        password = acct.get("password", "")
        log.info("Processing", extra={"username": username, "has_password": bool(password)})

        result = pipeline.execute(username, password)
        results.append({
            "username": username,
            "status": "active" if result.success else "failed",
            "last_result": result.message or ("签到成功" if result.success else "签到失败"),
            "balance": result.data.get("balance") if result.data else None,
            "checkin_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if result.success else None,
        })

        if i < len(accounts) - 1:
            if (i + 1) % 15 == 0:
                pause = 120
                log.info("Batch pause", extra={"completed": i + 1, "pause_sec": pause})
                time.sleep(pause)
            else:
                time.sleep(random.randint(15, 30))

    RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    success = sum(1 for r in results if r["status"] == "active")
    log.info("Batch checkin completed", extra={"success": success, "total": len(results)})


if __name__ == "__main__":
    run()
