"""Extract verification codes from email text."""

from __future__ import annotations

import re
import time
from html import unescape

from adapters.email.base import EmailClient, EmailMessage

# 6-digit verification code patterns
CODE_PATTERNS = [
    re.compile(r'(?:verification\s*code|验证码|Your code is|code is)[：:\s]*(\d{6})', re.IGNORECASE),
    re.compile(r'(?:is|为)[：:\s]*(\d{6})\b', re.IGNORECASE),
    re.compile(r'^\s*(\d{6})\s*$', re.MULTILINE),
    re.compile(r'>\s*(\d{6})\s*<'),
]

AWS_SENDERS = [
    'no-reply@signin.aws',
    'no-reply@login.awsapps.com',
    'noreply@amazon.com',
    'account-update@amazon.com',
    'no-reply@aws.amazon.com',
    'noreply@aws.amazon.com',
]


def html_to_text(html: str) -> str:
    if not html:
        return ''
    text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
    text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:p|div)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    return re.sub(r'[ \t]+', ' ', text).strip()


def extract_code(text: str) -> str | None:
    """Extract a 6-digit verification code from text, filtering false positives."""
    if not text:
        return None
    for pattern in CODE_PATTERNS:
        for match in pattern.finditer(text):
            code = match.group(1)
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            context = text[start:end]
            if f'#{code}' in context:
                continue
            if re.search(r'(?:color|rgb|rgba|hsl)', context, re.IGNORECASE):
                continue
            if re.search(r'\d{7,}', context):
                continue
            return code
    return None


def poll_verification_code(
    client: EmailClient,
    sender_filters: list[str] | None = None,
    timeout: int = 120,
    interval: int = 5,
) -> str | None:
    """Poll email client for a verification code until found or timeout."""
    senders = [s.lower() for s in (sender_filters or AWS_SENDERS)]
    checked_ids: set[str] = set()
    deadline = time.time() + timeout

    while time.time() < deadline:
        messages = client.fetch_recent_messages(limit=50)
        for msg in messages:
            if msg.id in checked_ids:
                continue
            checked_ids.add(msg.id)
            if not any(s in msg.sender.lower() for s in senders):
                continue
            code = extract_code(msg.body_text)
            if not code:
                code = extract_code(html_to_text(msg.body_text))
            if code:
                return code
        time.sleep(interval)
    return None
