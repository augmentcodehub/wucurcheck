"""Send a minimal chat message via Kiro generateAssistantResponse API.

Simulates Kiro IDE sending a chat message to trigger free trial activation.
"""
import json
import sys
import uuid

import httpx

ENDPOINT = "https://codewhisperer.us-east-1.amazonaws.com/generateAssistantResponse"
BUILDER_ID_PROFILE_ARN = "arn:aws:codewhisperer:us-east-1:638616132270:profile/AAAACCCCXXXX"
KIRO_VERSION = "0.12.200"
MACHINE_ID = "0" * 64


def send_chat(access_token: str, message: str = "hi") -> dict:
    """Send a minimal chat message to Kiro API (streaming endpoint)."""
    conversation_id = str(uuid.uuid4())

    payload = {
        "conversationState": {
            "chatTriggerType": "MANUAL",
            "conversationId": conversation_id,
            "currentMessage": {
                "userInputMessage": {
                    "content": message,
                    "modelId": "CLAUDE_SONNET_4_20250514_V1_0",
                    "origin": "AI_EDITOR",
                    "userInputMessageContext": {},
                }
            },
            "history": [],
        },
        "profileArn": BUILDER_ID_PROFILE_ARN,
    }

    headers = {
        "content-type": "application/json",
        "x-amzn-kiro-agent-mode": "spec",
        "Authorization": f"Bearer {access_token}",
        "user-agent": f"aws-sdk-js/1.0.34 ua/2.1 os/win32#10.0.0 lang/js md/nodejs#22.22.0 api/codewhispererstreaming#1.0.34 m/E KiroIDE-{KIRO_VERSION}-{MACHINE_ID}",
        "x-amz-user-agent": f"aws-sdk-js/1.0.34 KiroIDE {KIRO_VERSION} {MACHINE_ID}",
        "amz-sdk-invocation-id": str(uuid.uuid4()),
        "amz-sdk-request": "attempt=1; max=3",
    }

    try:
        resp = httpx.post(ENDPOINT, json=payload, headers=headers, timeout=30)
        return {"status": resp.status_code, "body": resp.text[:500]}
    except Exception as e:
        return {"status": -1, "error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python activate_chat.py <access_token>")
        sys.exit(1)

    token = sys.argv[1]
    print("Sending chat message to trigger trial...")
    result = send_chat(token)
    print(json.dumps(result, indent=2, ensure_ascii=False))
