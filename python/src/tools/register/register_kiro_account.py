"""AWS Builder ID (Kiro) automated registration via Playwright.

Faithfully ported from Kiro-auto-register/src/main/autoRegister.ts.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import httpx
from playwright.async_api import Page, async_playwright

from adapters.email.base import EmailClient
from adapters.email.code_extractor import poll_verification_code

FIRST_NAMES = ['James', 'Robert', 'John', 'Michael', 'David', 'William', 'Richard', 'Maria', 'Elizabeth', 'Jennifer', 'Linda', 'Barbara', 'Susan', 'Jessica']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Wilson', 'Anderson', 'Thomas', 'Taylor']
DEFAULT_PASSWORD = 'admin123456aA!'

OIDC_BASE = 'https://oidc.us-east-1.amazonaws.com'
START_URL = 'https://view.awsapps.com/start'
REGISTER_URL_TEMPLATE = 'https://view.awsapps.com/start/#/device?user_code={user_code}'
SCOPES = [
    'codewhisperer:analysis',
    'codewhisperer:completions',
    'codewhisperer:conversations',
    'codewhisperer:taskassist',
    'codewhisperer:transformations',
]


@dataclass(frozen=True)
class DeviceAuthInfo:
    client_id: str
    client_secret: str
    device_code: str
    user_code: str
    interval: int = 1


@dataclass(frozen=True)
class KiroRegistrationResult:
    success: bool
    sso_token: str | None = None
    name: str | None = None
    password: str | None = None
    error: str | None = None


# ============ Device Code ============

def obtain_device_code() -> DeviceAuthInfo | None:
    """Register OIDC client and start device authorization to get a fresh user_code."""
    # Step 1: Register OIDC client
    resp = httpx.post(
        f'{OIDC_BASE}/client/register',
        json={
            'clientName': 'Kiro Account Manager',
            'clientType': 'public',
            'scopes': SCOPES,
            'grantTypes': ['urn:ietf:params:oauth:grant-type:device_code', 'refresh_token'],
            'issuerUrl': START_URL,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return None
    reg = resp.json()

    # Step 2: Device authorization
    resp = httpx.post(
        f'{OIDC_BASE}/device_authorization',
        json={
            'clientId': reg['clientId'],
            'clientSecret': reg['clientSecret'],
            'startUrl': START_URL,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return None
    dev = resp.json()
    return DeviceAuthInfo(
        client_id=reg['clientId'],
        client_secret=reg['clientSecret'],
        device_code=dev['deviceCode'],
        user_code=dev['userCode'],
        interval=dev.get('interval', 1),
    )


# ============ Helpers (match original TS exactly) ============

async def _wait_and_fill(page: Page, selector: str, value: str, timeout: int = 30000) -> bool:
    """Wait for input to appear and fill it."""
    try:
        el = page.locator(selector).first
        await el.wait_for(state='visible', timeout=timeout)
        await page.wait_for_timeout(500)
        await el.clear()
        await el.fill(value)
        return True
    except Exception:
        return False


async def _wait_and_click_with_retry(page: Page, selector: str, timeout: int = 30000, max_retries: int = 3) -> bool:
    """Click button, then check for AWS error popup and retry if needed."""
    try:
        el = page.locator(selector).first
        await el.wait_for(state='visible', timeout=timeout)
        await page.wait_for_timeout(500)
        await el.click()
    except Exception:
        return False

    # Check for error popup and retry
    for retry in range(max_retries):
        await page.wait_for_timeout(1500)
        has_error = False
        for err_sel in ['[class*="awsui_content_"]', '.awsui-flash-error']:
            try:
                elements = await page.locator(err_sel).all()
                for elem in elements:
                    text = await elem.text_content()
                    if text and any(e in text for e in [
                        'error processing your request',
                        '抱歉，处理您的请求时出错',
                        'Please try again',
                    ]):
                        has_error = True
                        break
                if has_error:
                    break
            except Exception:
                continue

        if not has_error:
            return True

        if retry < max_retries - 1:
            await page.wait_for_timeout(2000)
            try:
                await page.locator(selector).first.click()
            except Exception:
                pass

    return False


# ============ Outlook Activation ============

async def activate_outlook(email: str, password: str, *, headless: bool = False) -> bool:
    """Activate an Outlook mailbox by logging in via browser."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, args=['--disable-blink-features=AutomationControlled'])
        ctx = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        page = await ctx.new_page()
        try:
            await page.goto('https://go.microsoft.com/fwlink/p/?linkid=2125442', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)

            # Email
            for sel in ['input#i0116[type="email"]', 'input[name="loginfmt"]', 'input[type="email"]']:
                if await _wait_and_fill(page, sel, email, timeout=10000):
                    break
            await page.wait_for_timeout(1000)

            # Next
            for sel in ['input#idSIButton9[type="submit"]', 'input[type="submit"]']:
                try:
                    await page.locator(sel).first.click()
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(3000)

            # Password
            for sel in ['input#i0118[type="password"]', 'input[name="passwd"]', 'input[type="password"]']:
                if await _wait_and_fill(page, sel, password, timeout=15000):
                    break
            await page.wait_for_timeout(1000)

            # Sign in
            for sel in ['button[type="submit"][data-testid="primaryButton"]', 'input#idSIButton9[type="submit"]']:
                try:
                    await page.locator(sel).first.click()
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(3000)

            # Skip prompts
            for _ in range(2):
                try:
                    await page.locator('a#iShowSkip').first.wait_for(state='visible', timeout=10000)
                    await page.locator('a#iShowSkip').first.click()
                    await page.wait_for_timeout(2000)
                except Exception:
                    break

            # Cancel passkey
            for sel in ['button[data-testid="secondaryButton"]:has-text("Cancel")', 'button[data-testid="secondaryButton"]:has-text("取消")']:
                try:
                    await page.locator(sel).first.wait_for(state='visible', timeout=5000)
                    await page.locator(sel).first.click()
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(2000)

            # Stay signed in - Yes
            for sel in ['input#idSIButton9', 'button:has-text("Yes")', 'button:has-text("是")']:
                try:
                    await page.locator(sel).first.wait_for(state='visible', timeout=5000)
                    await page.locator(sel).first.click()
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(5000)

            return 'outlook' in page.url.lower() or 'mail' in page.url.lower()
        finally:
            await browser.close()


# ============ Main Registration ============

async def register_kiro(
    email: str,
    email_client: EmailClient,
    *,
    proxy_url: str | None = None,
    headless: bool = False,
    code_timeout: int = 120,
) -> KiroRegistrationResult:
    """Register an AWS Builder ID account. Faithfully follows the original TS flow."""
    name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
    password = DEFAULT_PASSWORD

    # Obtain fresh device code
    device_auth = obtain_device_code()
    if not device_auth:
        return KiroRegistrationResult(False, error='Failed to obtain device code from AWS OIDC')

    register_url = REGISTER_URL_TEMPLATE.format(user_code=device_auth.user_code)

    async with async_playwright() as p:
        launch_opts: dict = {
            'headless': headless,
            'args': ['--disable-blink-features=AutomationControlled'],
        }
        if proxy_url:
            launch_opts['proxy'] = {'server': proxy_url}

        browser = await p.chromium.launch(**launch_opts)
        ctx = await browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        page = await ctx.new_page()

        try:
            # Step 1: Navigate to register page
            await page.goto(register_url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)

            # Fill email
            if not await _wait_and_fill(page, 'input[placeholder="username@example.com"]', email):
                return KiroRegistrationResult(False, error='Email input not found')
            await page.wait_for_timeout(1000)

            # Click first continue (with error retry)
            if not await _wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
                return KiroRegistrationResult(False, error='Click first continue failed')
            await page.wait_for_timeout(3000)

            # Detect flow: register vs login vs verify
            flow = await _detect_flow(page)

            if flow == 'register':
                # ===== REGISTER FLOW =====
                # Step 2: Fill name
                if not await _wait_and_fill(page, 'input[placeholder="Maria José Silva"]', name):
                    return KiroRegistrationResult(False, error='Name input not found')
                await page.wait_for_timeout(1000)

                # Click signup next
                if not await _wait_and_click_with_retry(page, 'button[data-testid="signup-next-button"]'):
                    return KiroRegistrationResult(False, error='Click signup next failed')
                await page.wait_for_timeout(3000)

                # Step 3: Wait for verification code input
                code_sel = await _find_code_input(page)
                if not code_sel:
                    return KiroRegistrationResult(False, error='Verification code input not found')
                await page.wait_for_timeout(1000)

                # Get code from email
                code = poll_verification_code(email_client, timeout=code_timeout)
                if not code:
                    return KiroRegistrationResult(False, error='Failed to get verification code')

                # Fill code
                if not await _wait_and_fill(page, code_sel, code):
                    return KiroRegistrationResult(False, error='Failed to fill verification code')
                await page.wait_for_timeout(1000)

                # Click verify
                if not await _wait_and_click_with_retry(page, 'button[data-testid="email-verification-verify-button"]'):
                    return KiroRegistrationResult(False, error='Click verify button failed')
                await page.wait_for_timeout(3000)

                # Step 4: Set password
                if not await _wait_and_fill(page, 'input[placeholder="Enter password"]', password):
                    return KiroRegistrationResult(False, error='Password input not found')
                await page.wait_for_timeout(500)
                if not await _wait_and_fill(page, 'input[placeholder="Re-enter password"]', password):
                    return KiroRegistrationResult(False, error='Confirm password input not found')
                await page.wait_for_timeout(1000)

                # Click final continue
                if not await _wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
                    return KiroRegistrationResult(False, error='Click final continue failed')
                await page.wait_for_timeout(5000)

            else:
                # ===== LOGIN FLOW (account already registered) =====
                if flow != 'verify':
                    # Need to enter password first
                    if not await _wait_and_fill(page, 'input[placeholder="Enter password"]', password):
                        return KiroRegistrationResult(False, error='Login password input not found')
                    await page.wait_for_timeout(1000)
                    if not await _wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
                        return KiroRegistrationResult(False, error='Click login continue failed')
                    await page.wait_for_timeout(3000)

                # Wait for code input
                code_sel = await _find_code_input(page)
                if not code_sel:
                    return KiroRegistrationResult(False, error='Login verification code input not found')
                await page.wait_for_timeout(1000)

                # Get code
                code = poll_verification_code(email_client, timeout=code_timeout)
                if not code:
                    return KiroRegistrationResult(False, error='Failed to get login verification code')

                # Fill code
                if not await _wait_and_fill(page, code_sel, code):
                    return KiroRegistrationResult(False, error='Failed to fill login code')
                await page.wait_for_timeout(1000)

                # Click verify
                if not await _wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
                    return KiroRegistrationResult(False, error='Click login verify failed')
                await page.wait_for_timeout(5000)

            # Step 5: Get SSO Token from cookies
            sso_token = None
            for _ in range(30):
                cookies = await ctx.cookies()
                for c in cookies:
                    if c['name'] == 'x-amz-sso_authn':
                        sso_token = c['value']
                        break
                if sso_token:
                    break
                await page.wait_for_timeout(1000)

            if sso_token:
                return KiroRegistrationResult(True, sso_token=sso_token, name=name, password=password)
            else:
                return KiroRegistrationResult(False, error='Failed to get SSO Token')

        except Exception as e:
            return KiroRegistrationResult(False, error=str(e))
        finally:
            await browser.close()


async def _detect_flow(page: Page) -> str:
    """Detect whether we're in register, login, or verify flow after first continue.
    
    Uses Promise.race pattern from original TS: wait for whichever element appears first.
    """
    import asyncio

    async def _wait(selector: str, label: str) -> str:
        try:
            await page.locator(selector).first.wait_for(state='visible', timeout=30000)
            return label
        except Exception:
            return ''

    results = await asyncio.gather(
        _wait('input[placeholder="Maria José Silva"]', 'register'),
        _wait('span[class*="awsui_heading-text"]:has-text("Sign in with your AWS Builder ID")', 'login'),
        _wait('span[class*="awsui_heading-text"]:has-text("Verify")', 'verify'),
        _wait('input[placeholder="6-digit"]', 'verify'),
    )

    for r in results:
        if r:
            return r

    # Fallback checks
    try:
        if await page.locator('input[placeholder="Maria José Silva"]').first.is_visible():
            return 'register'
    except Exception:
        pass
    try:
        if await page.locator('input[placeholder="6-digit"]').first.is_visible():
            return 'verify'
    except Exception:
        pass

    return 'login'


async def _find_code_input(page: Page) -> str | None:
    """Wait for verification code input to appear, return its selector."""
    for sel in ['input[placeholder="6-digit"]', 'input[placeholder="6 位数"]', 'input[class*="awsui_input"][type="text"]']:
        try:
            await page.locator(sel).first.wait_for(state='visible', timeout=10000)
            return sel
        except Exception:
            continue
    return None
