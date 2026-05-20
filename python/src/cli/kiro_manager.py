"""Kiro account manager CLI — check status, refresh tokens, batch operations.

Composition root: all dependencies are wired here, not inside use cases.

Usage:
    python -m cli.kiro_manager check --access-token xxx --refresh-token xxx
    python -m cli.kiro_manager batch --accounts-file accounts.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

log = logging.getLogger(__name__)


def _build_status_use_case():
    """Composition root: wire adapters into use case."""
    from adapters.kiro.api_client import KiroApiClient
    from adapters.token.oidc_token_service import OidcTokenService
    from adapters.token.social_token_service import SocialTokenService
    from core.application.check_account_status_use_case import CheckAccountStatusUseCase

    return CheckAccountStatusUseCase(
        api=KiroApiClient(),
        token_refreshers={
            "oidc": OidcTokenService(),
            "social": SocialTokenService(),
        },
    )


async def cmd_check(args) -> int:
    """Check a single account's status."""
    from core.application.check_account_status_use_case import AccountCredentials

    creds = AccountCredentials(
        access_token=args.access_token,
        refresh_token=args.refresh_token or "",
        client_id=args.client_id or "",
        client_secret=args.client_secret or "",
        region=args.region,
        auth_method=args.auth_method,
        idp=args.idp,
    )

    use_case = _build_status_use_case()
    result = await use_case.execute(creds)

    output = {
        "active": result.status.active,
        "suspended": result.status.suspended,
        "email": result.status.email,
        "subscription": result.status.subscription_type,
        "usage_current": result.status.usage.current,
        "usage_limit": result.status.usage.limit,
        "days_remaining": result.status.days_remaining,
        "token_refreshed": result.token_refreshed,
        "error": result.status.error,
    }

    if result.token_refreshed:
        output["new_access_token"] = result.new_access_token
        output["new_refresh_token"] = result.new_refresh_token

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if result.status.active else 1


async def cmd_batch(args) -> int:
    """Batch refresh and check multiple accounts."""
    from core.application.batch_refresh_use_case import BatchAccount, BatchRefreshUseCase
    from core.application.check_account_status_use_case import AccountCredentials

    data = json.loads(Path(args.accounts_file).read_text())
    accounts_raw = data if isinstance(data, list) else data.get("accounts", [])

    accounts = []
    for item in accounts_raw:
        creds = item.get("credentials", item)
        accounts.append(BatchAccount(
            id=item.get("id", item.get("username", "")),
            email=item.get("email", item.get("username", "")),
            credentials=AccountCredentials(
                access_token=creds.get("access_token", ""),
                refresh_token=creds.get("refresh_token", ""),
                client_id=creds.get("client_id", ""),
                client_secret=creds.get("client_secret", ""),
                region=creds.get("region", "us-east-1"),
                auth_method=creds.get("auth_method", "oidc"),
                idp=creds.get("idp", "BuilderId"),
            ),
        ))

    def on_progress(done: int, total: int) -> None:
        print(f"\r[{done}/{total}]", end="", flush=True)

    status_use_case = _build_status_use_case()
    batch_use_case = BatchRefreshUseCase(
        status_use_case=status_use_case,
        concurrency=args.concurrency,
    )
    summary = await batch_use_case.execute(accounts, on_progress=on_progress)
    print()

    output = {
        "total": summary.total,
        "success": summary.success,
        "failed": summary.failed,
        "suspended": summary.suspended,
        "results": [],
    }

    for r in summary.results:
        entry: dict = {"id": r.id, "email": r.email}
        if r.error:
            entry["status"] = "error"
            entry["error"] = r.error
        elif r.result:
            entry["status"] = (
                "active" if r.result.status.active
                else "suspended" if r.result.status.suspended
                else "error"
            )
            entry["usage"] = f"{r.result.status.usage.current}/{r.result.status.usage.limit}"
            entry["subscription"] = r.result.status.subscription_type
            if r.result.token_refreshed:
                entry["token_refreshed"] = True
        output["results"].append(entry)

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if summary.failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kiro account manager")
    sub = parser.add_subparsers(dest="command", required=True)

    # check subcommand
    p_check = sub.add_parser("check", help="Check single account status")
    p_check.add_argument("--access-token", required=True)
    p_check.add_argument("--refresh-token")
    p_check.add_argument("--client-id")
    p_check.add_argument("--client-secret")
    p_check.add_argument("--region", default="us-east-1")
    p_check.add_argument("--auth-method", choices=["oidc", "social"], default="oidc")
    p_check.add_argument("--idp", default="BuilderId", choices=["BuilderId", "Github", "Google"])

    # batch subcommand
    p_batch = sub.add_parser("batch", help="Batch refresh and check accounts")
    p_batch.add_argument("--accounts-file", required=True, help="JSON file with accounts")
    p_batch.add_argument("--concurrency", type=int, default=10)

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "check":
        return asyncio.run(cmd_check(args))
    elif args.command == "batch":
        return asyncio.run(cmd_batch(args))
    return 1


if __name__ == "__main__":
    sys.exit(main())
