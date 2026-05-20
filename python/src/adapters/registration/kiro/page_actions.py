"""Atomic Playwright page operations for Kiro registration flows."""

from __future__ import annotations

import asyncio
import logging

from playwright.async_api import Page

log = logging.getLogger(__name__)

_ERROR_INDICATORS = (
    "error processing your request",
    "抱歉，处理您的请求时出错",
    "Please try again",
)


async def wait_and_fill(page: Page, selector: str, value: str, timeout: int = 30000) -> bool:
    """Wait for an element to appear and fill it with a value."""
    try:
        el = page.locator(selector).first
        await el.wait_for(state="visible", timeout=timeout)
        await page.wait_for_timeout(500)
        await el.clear()
        await el.fill(value)
        return True
    except Exception as exc:
        log.debug("wait_and_fill failed: selector=%s error=%s", selector, exc)
        return False


async def wait_and_click(page: Page, selector: str, timeout: int = 30000, max_retries: int = 3) -> bool:
    """Click a button, detect AWS error banners, and retry if needed."""
    try:
        el = page.locator(selector).first
        await el.wait_for(state="visible", timeout=timeout)
        await page.wait_for_timeout(500)
        await el.click()
    except Exception as exc:
        log.debug("wait_and_click initial click failed: selector=%s error=%s", selector, exc)
        return False

    for retry in range(max_retries):
        await page.wait_for_timeout(1500)
        if not await _has_error_banner(page):
            return True
        if retry < max_retries - 1:
            log.debug("Error banner detected, retrying click (attempt %d)", retry + 2)
            await page.wait_for_timeout(2000)
            try:
                await page.locator(selector).first.click()
            except Exception:
                pass

    return False


async def detect_flow(page: Page) -> str:
    """Detect whether the current page shows register, login, or verify flow."""

    async def _probe(selector: str, label: str) -> str:
        try:
            await page.locator(selector).first.wait_for(state="visible", timeout=30000)
            return label
        except Exception:
            return ""

    results = await asyncio.gather(
        _probe('input[placeholder="Maria José Silva"]', "register"),
        _probe('span[class*="awsui_heading-text"]:has-text("Sign in with your AWS Builder ID")', "login"),
        _probe('span[class*="awsui_heading-text"]:has-text("Verify")', "verify"),
        _probe('input[placeholder="6-digit"]', "verify"),
    )

    for r in results:
        if r:
            return r

    # Fallback probes
    try:
        if await page.locator('input[placeholder="Maria José Silva"]').first.is_visible():
            return "register"
    except Exception:
        pass
    try:
        if await page.locator('input[placeholder="6-digit"]').first.is_visible():
            return "verify"
    except Exception:
        pass

    return "login"


async def find_code_input(page: Page) -> str | None:
    """Locate the verification code input field."""
    candidates = [
        'input[placeholder="6-digit"]',
        'input[placeholder="6 位数"]',
        'input[class*="awsui_input"][type="text"]',
    ]
    for sel in candidates:
        try:
            await page.locator(sel).first.wait_for(state="visible", timeout=10000)
            return sel
        except Exception:
            continue
    return None


async def _has_error_banner(page: Page) -> bool:
    """Check if an AWS error banner is visible on the page."""
    for err_sel in ['[class*="awsui_content_"]', ".awsui-flash-error"]:
        try:
            elements = await page.locator(err_sel).all()
            for elem in elements:
                text = await elem.text_content()
                if text and any(indicator in text for indicator in _ERROR_INDICATORS):
                    return True
        except Exception:
            continue
    return False
