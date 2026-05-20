"""Unified registration CLI — single entry point for all providers.

Usage:
    python -m cli.register --provider kiro --email-provider ouraihub --email-api-key xxx
    python -m cli.register --provider wucur --email user@example.com --password xxx
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

from core.application.register_account_use_case import RegisterAccountUseCase
from core.ports.registration_service import RegistrationConfig, RegistrationService
from core.registration import RegistrationResult

log = logging.getLogger(__name__)


def _build_email_client(args):
    """Construct email client from CLI args. Returns (client, email) or (None, None)."""
    import random
    import string

    from adapters.email.generic_api import GenericApiClient, GenericApiConfig
    from adapters.email.ouraihub import OuraihubClient, OuraihubConfig
    from adapters.email.outlook_graph import OutlookGraphClient

    if args.email_provider == "ouraihub":
        config = OuraihubConfig(
            api_key=args.email_api_key or "",
            domain=args.email_domain or "ouraihub.com",
            expiry_time=args.email_expiry or 3600000,
        )
        client = OuraihubClient(config)
        if args.email_id:
            client.set_email_id(args.email_id)
            email = args.email or f"unknown@{config.domain}"
        else:
            prefix = (
                args.email.split("@")[0]
                if args.email and "@" in args.email
                else "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
            )
            addr = client.create_email(prefix)
            if not addr:
                return None, None
            email = addr
            log.info("Created temp email: %s", email)
        return client, email

    if args.email_api_url:
        cfg = GenericApiConfig(
            api_url=args.email_api_url,
            api_key=args.email_api_key or "",
            extra_headers=json.loads(args.email_api_headers) if args.email_api_headers else {},
            messages_path=args.email_messages_path or "data",
            sender_field=args.email_sender_field or "from",
            body_field=args.email_body_field or "body",
        )
        return GenericApiClient(cfg), args.email

    if args.refresh_token and args.client_id:
        return OutlookGraphClient(args.refresh_token, args.client_id), args.email

    return None, args.email


def _build_services(args) -> dict[str, RegistrationService]:
    """Construct provider service registry from CLI args."""
    services: dict[str, RegistrationService] = {}

    # Kiro requires email client
    email_client, _ = _build_email_client(args)
    if email_client:
        from adapters.registration.kiro import KiroRegistrationService
        services["kiro"] = KiroRegistrationService(email_client)

    # Wucur is always available
    from adapters.registration.wucur import WucurRegistrationService
    services["wucur"] = WucurRegistrationService()

    return services


async def _run(args) -> int:
    # Resolve email
    if args.provider == "kiro":
        _, email = _build_email_client(args)
        if not email:
            log.error("Failed to resolve email address")
            return 1
    else:
        email = args.email
        if not email:
            log.error("--email is required for provider %s", args.provider)
            return 1

    services = _build_services(args)
    use_case = RegisterAccountUseCase(services)

    config = RegistrationConfig(
        proxy_url=args.proxy,
        headless=args.headless,
        code_timeout=args.code_timeout,
        max_retries=args.max_retries,
        password=args.password,
    )

    result = await use_case.execute(args.provider, email, config, password=args.password)
    _output_result(result, json_mode=args.json)
    return 0 if result.success else 1


def _output_result(result: RegistrationResult, *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(result.to_callback_dict(), ensure_ascii=False))
    elif result.success:
        print(f"[OK] Registration successful: {result.name or result.username} ({result.platform})")
    else:
        print(f"[FAILED] {result.error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register account for any provider.")
    parser.add_argument("--provider", required=True, choices=["kiro", "wucur"], help="Provider name")
    parser.add_argument("--email", help="Email address (auto-generated for ouraihub)")
    parser.add_argument("--password", help="Account password (auto-generated if omitted)")

    # Email provider options
    parser.add_argument("--email-provider", choices=["ouraihub", "outlook", "generic"], default="ouraihub")
    parser.add_argument("--email-api-key", help="Email API key")
    parser.add_argument("--email-domain", default="ouraihub.com")
    parser.add_argument("--email-id", help="Existing email ID (ouraihub)")
    parser.add_argument("--email-expiry", type=int, default=3600000)
    parser.add_argument("--email-api-url", help="Custom email API URL")
    parser.add_argument("--email-api-headers", help="Extra headers as JSON")
    parser.add_argument("--email-messages-path", default="data")
    parser.add_argument("--email-sender-field", default="from")
    parser.add_argument("--email-body-field", default="body")
    parser.add_argument("--refresh-token", help="Outlook OAuth2 refresh token")
    parser.add_argument("--client-id", help="Outlook Graph API client ID")

    # Registration options
    parser.add_argument("--proxy", help="Proxy URL")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--code-timeout", type=int, default=120)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
