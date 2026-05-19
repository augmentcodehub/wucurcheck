#!/usr/bin/env python3
"""CLI entry point for Kiro (AWS Builder ID) account registration."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import string
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.email.generic_api import GenericApiClient, GenericApiConfig
from adapters.email.ouraihub import OuraihubClient, OuraihubConfig
from adapters.email.outlook_graph import OutlookGraphClient
from tools.register.register_kiro_account import activate_outlook, register_kiro, KiroRegistrationResult


def _random_prefix(length: int = 10) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def build_email_client(args) -> tuple[object | None, str | None]:
    """Build email client and resolve email address. Returns (client, email)."""
    if args.email_provider == 'ouraihub':
        config = OuraihubConfig(
            api_key=args.email_api_key or '',
            domain=args.email_domain or 'ouraihub.com',
            expiry_time=args.email_expiry or 3600000,
        )
        client = OuraihubClient(config)
        if args.email_id:
            client.set_email_id(args.email_id)
            email = args.email or f'unknown@{config.domain}'
        else:
            # Auto-generate random prefix
            prefix = args.email.split('@')[0] if args.email and '@' in args.email else _random_prefix()
            addr = client.create_email(prefix)
            if not addr:
                return None, None
            email = addr
            print(f'[INFO] Created temp email: {email}')
        return client, email

    if args.email_api_url:
        cfg = GenericApiConfig(
            api_url=args.email_api_url,
            api_key=args.email_api_key or '',
            extra_headers=json.loads(args.email_api_headers) if args.email_api_headers else {},
            messages_path=args.email_messages_path or 'data',
            sender_field=args.email_sender_field or 'from',
            body_field=args.email_body_field or 'body',
        )
        return GenericApiClient(cfg), args.email

    if args.refresh_token and args.client_id:
        return OutlookGraphClient(args.refresh_token, args.client_id), args.email

    return None, args.email


async def run(args) -> int:
    # Build email client (may auto-generate email address)
    client, email = build_email_client(args)
    if not client:
        print('[ERROR] Must provide --email-api-key (ouraihub), --refresh-token + --client-id (outlook), or --email-api-url (generic)', file=sys.stderr)
        return 1
    if not email:
        print('[ERROR] Failed to create temp email', file=sys.stderr)
        return 1

    # Activate Outlook if requested
    if args.activate and args.email_password:
        print(f'[INFO] Activating Outlook mailbox: {email}')
        ok = await activate_outlook(email, args.email_password, headless=args.headless)
        if not ok:
            print('[WARN] Outlook activation may not have completed')
        else:
            print('[OK] Outlook activated')

    # Register
    result = await register_kiro(
        email=email,
        email_client=client,
        proxy_url=args.proxy,
        headless=args.headless,
        code_timeout=args.code_timeout,
    )

    if args.json:
        print(json.dumps({
            'success': result.success,
            'email': email,
            'sso_token': result.sso_token,
            'access_token': result.access_token,
            'refresh_token': result.refresh_token,
            'client_id': result.client_id,
            'client_secret': result.client_secret,
            'region': result.region,
            'expires_in': result.expires_in,
            'name': result.name,
            'password': result.password,
            'error': result.error,
        }, ensure_ascii=False))
    else:
        if result.success:
            print(f'[OK] Registration successful: {result.name} ({email})')
            if result.sso_token:
                print(f'[OK] SSO Token: {result.sso_token[:50]}...')
        else:
            print(f'[FAILED] {result.error}')

    return 0 if result.success else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Register a Kiro (AWS Builder ID) account.')
    parser.add_argument('--email', help='Email address (auto-generated for ouraihub if omitted)')
    parser.add_argument('--email-password', help='Email password (for Outlook activation)')
    parser.add_argument('--refresh-token', help='Outlook OAuth2 refresh token')
    parser.add_argument('--client-id', help='Outlook Graph API client ID')
    # OurAIHub temp email options
    parser.add_argument('--email-provider', choices=['outlook', 'ouraihub', 'generic'], default='outlook', help='Email provider type')
    parser.add_argument('--email-api-key', help='Email API key')
    parser.add_argument('--email-domain', default='ouraihub.com', help='Temp email domain (ouraihub)')
    parser.add_argument('--email-id', help='Existing email ID (ouraihub)')
    parser.add_argument('--email-expiry', type=int, default=3600000, help='Temp email expiry in ms (ouraihub)')
    # Generic email API options
    parser.add_argument('--email-api-url', help='Custom email API URL')
    parser.add_argument('--email-api-headers', help='Extra headers as JSON object')
    parser.add_argument('--email-messages-path', default='data', help='JSON path to messages list')
    parser.add_argument('--email-sender-field', default='from', help='Field name for sender')
    parser.add_argument('--email-body-field', default='body', help='Field name for body')
    # Registration options
    parser.add_argument('--proxy', help='Proxy URL for registration browser')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--activate', action='store_true', help='Activate Outlook mailbox first')
    parser.add_argument('--code-timeout', type=int, default=120, help='Verification code timeout (seconds)')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    args = parser.parse_args(argv)

    return asyncio.run(run(args))


if __name__ == '__main__':
    sys.exit(main())
