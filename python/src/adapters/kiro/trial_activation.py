"""Trigger Kiro free trial by sending a minimal chat message.

Called after registration to activate the 500 bonus credits.
Uses the generateAssistantResponse streaming API (same as Kiro IDE).
"""

from __future__ import annotations

import logging
import uuid

import httpx

log = logging.getLogger(__name__)

ENDPOINT = "https://codewhisperer.us-east-1.amazonaws.com/generateAssistantResponse"
BUILDER_ID_PROFILE_ARN = "arn:aws:codewhisperer:us-east-1:638616132270:profile/AAAACCCCXXXX"
KIRO_VERSION = "0.12.200"
MACHINE_ID = "0" * 64


async def activate_trial(access_token: str) -> dict:
    """Send a single chat message to trigger trial activation.

    Args:
        access_token: Valid Kiro access token.

    Returns:
        {"success": True/False, "status": int, "error": str|None}
    """
    payload = {
        "conversationState": {
            "chatTriggerType": "MANUAL",
            "conversationId": str(uuid.uuid4()),
            "currentMessage": {
                "userInputMessage": {
                    "content": "hello",
                    "origin": "AI_EDITOR",
                }
            },
        },
        "profileArn": BUILDER_ID_PROFILE_ARN,
    }

    headers = {
        "content-type": "application/json",
        "x-amz-target": "AmazonCodeWhispererStreamingService.GenerateAssistantResponse",
        "Authorization": f"Bearer {access_token}",
        "user-agent": (
            f"aws-sdk-js/1.0.34 ua/2.1 os/win32#10.0.0 lang/js md/nodejs#22.22.0 "
            f"api/codewhispererstreaming#1.0.34 m/E KiroIDE-{KIRO_VERSION}-{MACHINE_ID}"
        ),
        "amz-sdk-invocation-id": str(uuid.uuid4()),
        "amz-sdk-request": "attempt=1; max=3",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(ENDPOINT, json=payload, headers=headers)

        if resp.status_code == 200:
            log.info("trial_activation_sent", extra={"status": 200})
            return {"success": True, "status": 200, "error": None}

        error = resp.text[:200]
        log.warning("trial_activation_failed", extra={"status": resp.status_code, "error": error})
        return {"success": False, "status": resp.status_code, "error": error}

    except Exception as exc:
        log.error("trial_activation_error", extra={"error": str(exc)})
        return {"success": False, "status": -1, "error": str(exc)}
