"""Kiro browser registration flow — Page Object orchestration.

Manages the full Playwright lifecycle: launch → navigate → register/login → extract sso_token.
"""

from __future__ import annotations

import logging
import random
import time

from playwright.async_api import async_playwright

from adapters.email.base import EmailClient
from adapters.email.code_extractor import poll_verification_code
from core.ports.registration_service import RegistrationConfig

from .constants import FIRST_NAMES, LAST_NAMES
from .device_code import obtain_device_code
from .page_actions import detect_flow, find_code_input, wait_and_click, wait_and_fill

log = logging.getLogger(__name__)


class KiroBrowserFlow:
    """Encapsulates the complete Kiro browser registration flow."""

    def __init__(self, email: str, password: str, email_client: EmailClient, config: RegistrationConfig) -> None:
        self.email = email
        self.password = password
        self.name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        self._email_client = email_client
        self._config = config

    async def execute(self) -> str | None:
        """Run the browser flow. Returns sso_token on success, 'ERROR:...' on failure."""
        device_auth = obtain_device_code()
        if not device_auth:
            return "ERROR:Failed to obtain device code from AWS OIDC"

        register_url = f'https://view.awsapps.com/start/#/device?user_code={device_auth["user_code"]}'
        log.info("Starting browser flow for %s", self.email)

        async with async_playwright() as p:
            launch_opts: dict = {
                "headless": self._config.headless,
                "args": ["--disable-blink-features=AutomationControlled"],
            }
            if self._config.proxy_url:
                launch_opts["proxy"] = {"server": self._config.proxy_url}

            browser = await p.chromium.launch(**launch_opts)
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await ctx.new_page()

            try:
                await page.goto(register_url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(2000)

                # Fill email
                if not await wait_and_fill(page, 'input[placeholder="username@example.com"]', self.email):
                    return "ERROR:Email input not found"
                await page.wait_for_timeout(1000)

                # Click continue
                if not await wait_and_click(page, 'button[data-testid="test-primary-button"]'):
                    return "ERROR:Click first continue failed"
                await page.wait_for_timeout(3000)

                # Detect and handle flow
                flow = await detect_flow(page)
                log.info("Detected flow: %s", flow)

                if flow == "register":
                    err = await self._register_flow(page)
                else:
                    err = await self._login_flow(page, is_verify=(flow == "verify"))

                if err:
                    return err

                # Extract sso_token from cookies
                return await self._extract_sso_token(ctx, page)

            except Exception as exc:
                log.exception("Browser flow failed")
                return f"ERROR:{exc}"
            finally:
                await browser.close()

    async def _register_flow(self, page) -> str | None:
        """New account registration sub-flow."""
        if not await wait_and_fill(page, 'input[placeholder="Maria José Silva"]', self.name):
            return "ERROR:Name input not found"
        await page.wait_for_timeout(1000)

        if not await wait_and_click(page, 'button[data-testid="signup-next-button"]'):
            return "ERROR:Click signup next failed"
        await page.wait_for_timeout(3000)

        # Verify email code
        err = await self._enter_verification_code(page)
        if err:
            return err

        if not await wait_and_click(page, 'button[data-testid="email-verification-verify-button"]'):
            return "ERROR:Click verify button failed"
        await page.wait_for_timeout(3000)

        # Set password
        if not await wait_and_fill(page, 'input[placeholder="Enter password"]', self.password):
            return "ERROR:Password input not found"
        await page.wait_for_timeout(500)
        if not await wait_and_fill(page, 'input[placeholder="Re-enter password"]', self.password):
            return "ERROR:Confirm password input not found"
        await page.wait_for_timeout(1000)

        if not await wait_and_click(page, 'button[data-testid="test-primary-button"]'):
            return "ERROR:Click final continue failed"
        await page.wait_for_timeout(5000)
        return None

    async def _login_flow(self, page, *, is_verify: bool = False) -> str | None:
        """Existing account login sub-flow."""
        if not is_verify:
            if not await wait_and_fill(page, 'input[placeholder="Enter password"]', self.password):
                return "ERROR:Login password input not found"
            await page.wait_for_timeout(1000)
            if not await wait_and_click(page, 'button[data-testid="test-primary-button"]'):
                return "ERROR:Click login continue failed"
            await page.wait_for_timeout(3000)

        err = await self._enter_verification_code(page)
        if err:
            return err

        if not await wait_and_click(page, 'button[data-testid="test-primary-button"]'):
            return "ERROR:Click login verify failed"
        await page.wait_for_timeout(5000)
        return None

    async def _enter_verification_code(self, page) -> str | None:
        """Wait for code input, poll email, fill code. Resend if first attempt times out."""
        code_sel = await find_code_input(page)
        if not code_sel:
            return "ERROR:Verification code input not found"
        await page.wait_for_timeout(1000)

        # First attempt (60s)
        code = poll_verification_code(self._email_client, timeout=min(60, self._config.code_timeout))

        if not code:
            # Try resend
            resend = page.locator('[data-testid="resend-code"], :text("Resend"), :text("重新发送")')
            if await resend.count() > 0:
                await resend.first.click()
                log.info("Clicked resend code button for %s", self.email)
            # Second attempt
            code = poll_verification_code(self._email_client, timeout=60)

        if not code:
            return "ERROR:Failed to get verification code"

        if not await wait_and_fill(page, code_sel, code):
            return "ERROR:Failed to fill verification code"
        await page.wait_for_timeout(1000)
        return None

    async def _extract_sso_token(self, ctx, page) -> str | None:
        """Poll cookies for the sso_token."""
        for _ in range(30):
            cookies = await ctx.cookies()
            for c in cookies:
                if c["name"] == "x-amz-sso_authn":
                    log.info("SSO token extracted (length=%d)", len(c["value"]))
                    return c["value"]
            await page.wait_for_timeout(1000)
        return "ERROR:Failed to get SSO Token cookie"
