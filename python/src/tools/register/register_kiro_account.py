"""AWS Builder ID (Kiro) automated registration via Playwright.

Faithfully ported from Kiro-auto-register/src/main/autoRegister.ts + index.ts.
Flow: browser registration → sso_token cookie → ssoDeviceAuth API → refreshToken + accessToken.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field

import httpx
from playwright.async_api import Page, async_playwright

from adapters.email.base import EmailClient
from adapters.email.code_extractor import poll_verification_code

FIRST_NAMES = ['James', 'Robert', 'John', 'Michael', 'David', 'William', 'Richard', 'Maria', 'Elizabeth', 'Jennifer', 'Linda', 'Barbara', 'Susan', 'Jessica']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Wilson', 'Anderson', 'Thomas', 'Taylor']
DEFAULT_PASSWORD = 'admin123456aA!'

OIDC_BASE = 'https://oidc.us-east-1.amazonaws.com'
PORTAL_BASE = 'https://portal.sso.us-east-1.amazonaws.com'
START_URL = 'https://view.awsapps.com/start'
SCOPES = [
    'codewhisperer:analysis',
    'codewhisperer:completions',
    'codewhisperer:conversations',
    'codewhisperer:taskassist',
    'codewhisperer:transformations',
]


@dataclass(frozen=True)
class KiroRegistrationResult:
    success: bool
    sso_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    region: str = 'us-east-1'
    expires_in: int | None = None
    name: str | None = None
    password: str | None = None
    error: str | None = None


# ============ SSO Device Auth (from index.ts ssoDeviceAuth) ============

def sso_device_auth(bearer_token: str, region: str = 'us-east-1') -> dict:
    """Execute the full SSO device authorization flow using the bearer token (sso_token).

    Returns dict with: success, accessToken, refreshToken, clientId, clientSecret, region, expiresIn, error
    """
    oidc_base = f'https://oidc.{region}.amazonaws.com'
    portal_base = 'https://portal.sso.us-east-1.amazonaws.com'
    start_url = 'https://view.awsapps.com/start'
    scopes = SCOPES

    with httpx.Client(timeout=30) as client:
        # Step 1: Register OIDC client
        print('[SSO] Step 1: Registering OIDC client...')
        resp = client.post(f'{oidc_base}/client/register', json={
            'clientName': 'Kiro Account Manager',
            'clientType': 'public',
            'scopes': scopes,
            'grantTypes': ['urn:ietf:params:oauth:grant-type:device_code', 'refresh_token'],
            'issuerUrl': start_url,
        })
        if resp.status_code != 200:
            return {'success': False, 'error': f'Register client failed: {resp.status_code} {resp.text[:200]}'}
        reg = resp.json()
        client_id = reg['clientId']
        client_secret = reg['clientSecret']
        print(f'[SSO] Client registered: {client_id[:30]}...')

        # Step 2: Device authorization
        print('[SSO] Step 2: Starting device authorization...')
        resp = client.post(f'{oidc_base}/device_authorization', json={
            'clientId': client_id,
            'clientSecret': client_secret,
            'startUrl': start_url,
        })
        if resp.status_code != 200:
            return {'success': False, 'error': f'Device auth failed: {resp.status_code} {resp.text[:200]}'}
        dev = resp.json()
        device_code = dev['deviceCode']
        user_code = dev['userCode']
        interval = dev.get('interval', 1)
        print(f'[SSO] Device code obtained, user_code: {user_code}')

        # Step 3: Verify bearer token (whoAmI)
        print('[SSO] Step 3: Verifying bearer token...')
        resp = client.get(f'{portal_base}/token/whoAmI', headers={
            'Authorization': f'Bearer {bearer_token}',
            'Accept': 'application/json',
        })
        if resp.status_code != 200:
            return {'success': False, 'error': f'whoAmI failed: {resp.status_code} {resp.text[:200]}'}
        print('[SSO] Bearer token verified')

        # Step 4: Get device session token
        print('[SSO] Step 4: Getting device session token...')
        resp = client.post(f'{portal_base}/session/device', headers={
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
        }, json={})
        if resp.status_code != 200:
            return {'success': False, 'error': f'Device session failed: {resp.status_code} {resp.text[:200]}'}
        device_session_token = resp.json()['token']
        print('[SSO] Device session token obtained')

        # Step 5: Accept user code
        print('[SSO] Step 5: Accepting user code...')
        resp = client.post(f'{oidc_base}/device_authorization/accept_user_code', headers={
            'Content-Type': 'application/json',
            'Referer': 'https://view.awsapps.com/',
        }, json={
            'userCode': user_code,
            'userSessionId': device_session_token,
        })
        if resp.status_code != 200:
            return {'success': False, 'error': f'Accept user code failed: {resp.status_code} {resp.text[:200]}'}
        accept_data = resp.json()
        device_context = accept_data.get('deviceContext')
        print('[SSO] User code accepted')

        # Step 6: Approve authorization
        if device_context and device_context.get('deviceContextId'):
            print('[SSO] Step 6: Approving authorization...')
            resp = client.post(f'{oidc_base}/device_authorization/associate_token', headers={
                'Content-Type': 'application/json',
                'Referer': 'https://view.awsapps.com/',
            }, json={
                'deviceContext': {
                    'deviceContextId': device_context['deviceContextId'],
                    'clientId': device_context.get('clientId', client_id),
                    'clientType': device_context.get('clientType', 'public'),
                },
                'userSessionId': device_session_token,
            })
            if resp.status_code != 200:
                return {'success': False, 'error': f'Approve failed: {resp.status_code} {resp.text[:200]}'}
            print('[SSO] Authorization approved')

        # Step 7: Poll for token
        print('[SSO] Step 7: Polling for token...')
        start_time = time.time()
        timeout = 120  # 2 minutes

        while time.time() - start_time < timeout:
            time.sleep(interval)
            resp = client.post(f'{oidc_base}/token', json={
                'clientId': client_id,
                'clientSecret': client_secret,
                'grantType': 'urn:ietf:params:oauth:grant-type:device_code',
                'deviceCode': device_code,
            })

            if resp.status_code == 200:
                token_data = resp.json()
                print('[SSO] Token obtained successfully!')
                return {
                    'success': True,
                    'accessToken': token_data['accessToken'],
                    'refreshToken': token_data['refreshToken'],
                    'clientId': client_id,
                    'clientSecret': client_secret,
                    'region': region,
                    'expiresIn': token_data.get('expiresIn'),
                }

            if resp.status_code == 400:
                err = resp.json()
                if err.get('error') == 'authorization_pending':
                    continue
                elif err.get('error') == 'slow_down':
                    interval += 5
                else:
                    return {'success': False, 'error': f'Token poll failed: {err.get("error")}'}

        return {'success': False, 'error': 'Authorization timeout'}


# ============ Browser Helpers ============

async def _wait_and_fill(page: Page, selector: str, value: str, timeout: int = 30000) -> bool:
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
    try:
        el = page.locator(selector).first
        await el.wait_for(state='visible', timeout=timeout)
        await page.wait_for_timeout(500)
        await el.click()
    except Exception:
        return False

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
            for sel in ['input#i0116[type="email"]', 'input[name="loginfmt"]', 'input[type="email"]']:
                if await _wait_and_fill(page, sel, email, timeout=10000):
                    break
            await page.wait_for_timeout(1000)
            for sel in ['input#idSIButton9[type="submit"]', 'input[type="submit"]']:
                try:
                    await page.locator(sel).first.click()
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(3000)
            for sel in ['input#i0118[type="password"]', 'input[name="passwd"]', 'input[type="password"]']:
                if await _wait_and_fill(page, sel, password, timeout=15000):
                    break
            await page.wait_for_timeout(1000)
            for sel in ['button[type="submit"][data-testid="primaryButton"]', 'input#idSIButton9[type="submit"]']:
                try:
                    await page.locator(sel).first.click()
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(3000)
            for _ in range(2):
                try:
                    await page.locator('a#iShowSkip').first.wait_for(state='visible', timeout=10000)
                    await page.locator('a#iShowSkip').first.click()
                    await page.wait_for_timeout(2000)
                except Exception:
                    break
            for sel in ['button[data-testid="secondaryButton"]:has-text("Cancel")', 'button[data-testid="secondaryButton"]:has-text("取消")']:
                try:
                    await page.locator(sel).first.wait_for(state='visible', timeout=5000)
                    await page.locator(sel).first.click()
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(2000)
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
    """Register an AWS Builder ID account. Strictly follows the original TS flow:
    1. Browser registration → get sso_token cookie
    2. ssoDeviceAuth(sso_token) → get refreshToken + accessToken + clientId + clientSecret
    """
    name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
    password = DEFAULT_PASSWORD

    # Phase 1: Browser registration to get sso_token
    sso_token = await _browser_register(email, email_client, name, password, proxy_url=proxy_url, headless=headless, code_timeout=code_timeout)

    if isinstance(sso_token, str) and sso_token.startswith('ERROR:'):
        return KiroRegistrationResult(False, error=sso_token[6:])

    if not sso_token:
        return KiroRegistrationResult(False, error='Failed to get SSO Token from browser')

    print(f'[OK] Got SSO Token (length={len(sso_token)})')

    # Phase 2: SSO Device Auth to get refreshToken + accessToken
    print('[INFO] Starting SSO Device Auth flow...')
    auth_result = sso_device_auth(sso_token)

    if not auth_result.get('success'):
        # Still return sso_token even if device auth fails
        return KiroRegistrationResult(
            success=True,
            sso_token=sso_token,
            name=name,
            password=password,
            error=f'Device auth failed: {auth_result.get("error")} (sso_token still valid)',
        )

    return KiroRegistrationResult(
        success=True,
        sso_token=sso_token,
        access_token=auth_result['accessToken'],
        refresh_token=auth_result['refreshToken'],
        client_id=auth_result['clientId'],
        client_secret=auth_result['clientSecret'],
        region=auth_result.get('region', 'us-east-1'),
        expires_in=auth_result.get('expiresIn'),
        name=name,
        password=password,
    )


async def _browser_register(
    email: str,
    email_client: EmailClient,
    name: str,
    password: str,
    *,
    proxy_url: str | None = None,
    headless: bool = False,
    code_timeout: int = 120,
) -> str | None:
    """Browser automation to register/login and get sso_token cookie. Returns token or 'ERROR:msg'."""

    # Get a fresh device code for the registration URL
    device_auth = _obtain_device_code()
    if not device_auth:
        return 'ERROR:Failed to obtain device code from AWS OIDC'

    register_url = f'https://view.awsapps.com/start/#/device?user_code={device_auth["user_code"]}'

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
            await page.goto(register_url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)

            # Fill email
            if not await _wait_and_fill(page, 'input[placeholder="username@example.com"]', email):
                return 'ERROR:Email input not found'
            await page.wait_for_timeout(1000)

            # Click first continue
            if not await _wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
                return 'ERROR:Click first continue failed'
            await page.wait_for_timeout(3000)

            # Detect flow
            flow = await _detect_flow(page)

            if flow == 'register':
                result = await _handle_register_flow(page, email_client, name, password, code_timeout)
            else:
                result = await _handle_login_flow(page, email_client, password, code_timeout, is_verify=(flow == 'verify'))

            if result:
                return result  # error string

            # Get SSO Token from cookies
            for _ in range(30):
                cookies = await ctx.cookies()
                for c in cookies:
                    if c['name'] == 'x-amz-sso_authn':
                        return c['value']
                await page.wait_for_timeout(1000)

            return 'ERROR:Failed to get SSO Token cookie'

        except Exception as e:
            return f'ERROR:{e}'
        finally:
            await browser.close()


def _obtain_device_code() -> dict | None:
    """Get a fresh device code for the registration URL only."""
    resp = httpx.post(f'{OIDC_BASE}/client/register', json={
        'clientName': 'Kiro Account Manager',
        'clientType': 'public',
        'scopes': SCOPES,
        'grantTypes': ['urn:ietf:params:oauth:grant-type:device_code', 'refresh_token'],
        'issuerUrl': START_URL,
    }, timeout=30)
    if resp.status_code != 200:
        return None
    reg = resp.json()

    resp = httpx.post(f'{OIDC_BASE}/device_authorization', json={
        'clientId': reg['clientId'],
        'clientSecret': reg['clientSecret'],
        'startUrl': START_URL,
    }, timeout=30)
    if resp.status_code != 200:
        return None
    dev = resp.json()
    return {'user_code': dev['userCode']}


async def _handle_register_flow(page: Page, email_client: EmailClient, name: str, password: str, code_timeout: int) -> str | None:
    """Handle new account registration. Returns None on success, error string on failure."""
    if not await _wait_and_fill(page, 'input[placeholder="Maria José Silva"]', name):
        return 'ERROR:Name input not found'
    await page.wait_for_timeout(1000)

    if not await _wait_and_click_with_retry(page, 'button[data-testid="signup-next-button"]'):
        return 'ERROR:Click signup next failed'
    await page.wait_for_timeout(3000)

    code_sel = await _find_code_input(page)
    if not code_sel:
        return 'ERROR:Verification code input not found'
    await page.wait_for_timeout(1000)

    code = poll_verification_code(email_client, timeout=code_timeout)
    if not code:
        return 'ERROR:Failed to get verification code'

    if not await _wait_and_fill(page, code_sel, code):
        return 'ERROR:Failed to fill verification code'
    await page.wait_for_timeout(1000)

    if not await _wait_and_click_with_retry(page, 'button[data-testid="email-verification-verify-button"]'):
        return 'ERROR:Click verify button failed'
    await page.wait_for_timeout(3000)

    if not await _wait_and_fill(page, 'input[placeholder="Enter password"]', password):
        return 'ERROR:Password input not found'
    await page.wait_for_timeout(500)
    if not await _wait_and_fill(page, 'input[placeholder="Re-enter password"]', password):
        return 'ERROR:Confirm password input not found'
    await page.wait_for_timeout(1000)

    if not await _wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
        return 'ERROR:Click final continue failed'
    await page.wait_for_timeout(5000)
    return None


async def _handle_login_flow(page: Page, email_client: EmailClient, password: str, code_timeout: int, *, is_verify: bool = False) -> str | None:
    """Handle login flow (account already registered). Returns None on success, error string on failure."""
    if not is_verify:
        if not await _wait_and_fill(page, 'input[placeholder="Enter password"]', password):
            return 'ERROR:Login password input not found'
        await page.wait_for_timeout(1000)
        if not await _wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
            return 'ERROR:Click login continue failed'
        await page.wait_for_timeout(3000)

    code_sel = await _find_code_input(page)
    if not code_sel:
        return 'ERROR:Login verification code input not found'
    await page.wait_for_timeout(1000)

    code = poll_verification_code(email_client, timeout=code_timeout)
    if not code:
        return 'ERROR:Failed to get login verification code'

    if not await _wait_and_fill(page, code_sel, code):
        return 'ERROR:Failed to fill login code'
    await page.wait_for_timeout(1000)

    if not await _wait_and_click_with_retry(page, 'button[data-testid="test-primary-button"]'):
        return 'ERROR:Click login verify failed'
    await page.wait_for_timeout(5000)
    return None


async def _detect_flow(page: Page) -> str:
    """Detect whether we're in register, login, or verify flow."""
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
    for sel in ['input[placeholder="6-digit"]', 'input[placeholder="6 位数"]', 'input[class*="awsui_input"][type="text"]']:
        try:
            await page.locator(sel).first.wait_for(state='visible', timeout=10000)
            return sel
        except Exception:
            continue
    return None
