"""SSO Device Auth — exchange sso_token for refreshToken + accessToken.

Faithfully ported from Kiro-auto-register/src/main/index.ts ssoDeviceAuth.
7-step flow: register client → device auth → whoAmI → session → accept → approve → poll token.
"""

from __future__ import annotations

import logging
import time

import httpx

from .constants import OIDC_BASE, SCOPES, START_URL

log = logging.getLogger(__name__)


def sso_device_auth(bearer_token: str, region: str = "us-east-1") -> dict:
    """Execute the full SSO device authorization flow.

    Args:
        bearer_token: The x-amz-sso_authn cookie value.
        region: AWS region for OIDC endpoint.

    Returns:
        Dict with keys: success, accessToken, refreshToken, clientId, clientSecret, region, expiresIn, error.
    """
    oidc_base = f"https://oidc.{region}.amazonaws.com"
    portal_base = "https://portal.sso.us-east-1.amazonaws.com"

    with httpx.Client(timeout=30) as client:
        # Step 1: Register OIDC client
        log.info("[SSO] Step 1: Registering OIDC client")
        resp = client.post(f"{oidc_base}/client/register", json={
            "clientName": "Kiro Account Manager",
            "clientType": "public",
            "scopes": SCOPES,
            "grantTypes": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
            "issuerUrl": START_URL,
        })
        if resp.status_code != 200:
            return _fail(f"Register client failed: {resp.status_code} {resp.text[:200]}")
        reg = resp.json()
        client_id = reg["clientId"]
        client_secret = reg["clientSecret"]

        # Step 2: Device authorization
        log.info("[SSO] Step 2: Starting device authorization")
        resp = client.post(f"{oidc_base}/device_authorization", json={
            "clientId": client_id,
            "clientSecret": client_secret,
            "startUrl": START_URL,
        })
        if resp.status_code != 200:
            return _fail(f"Device auth failed: {resp.status_code} {resp.text[:200]}")
        dev = resp.json()
        device_code = dev["deviceCode"]
        user_code = dev["userCode"]
        interval = dev.get("interval", 1)

        # Step 3: Verify bearer token
        log.info("[SSO] Step 3: Verifying bearer token")
        resp = client.get(f"{portal_base}/token/whoAmI", headers={
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
        })
        if resp.status_code != 200:
            return _fail(f"whoAmI failed: {resp.status_code} {resp.text[:200]}")

        # Step 4: Get device session token
        log.info("[SSO] Step 4: Getting device session token")
        resp = client.post(f"{portal_base}/session/device", headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }, json={})
        if resp.status_code != 200:
            return _fail(f"Device session failed: {resp.status_code} {resp.text[:200]}")
        device_session_token = resp.json()["token"]

        # Step 5: Accept user code
        log.info("[SSO] Step 5: Accepting user code %s", user_code)
        resp = client.post(f"{oidc_base}/device_authorization/accept_user_code", headers={
            "Content-Type": "application/json",
            "Referer": "https://view.awsapps.com/",
        }, json={
            "userCode": user_code,
            "userSessionId": device_session_token,
        })
        if resp.status_code != 200:
            return _fail(f"Accept user code failed: {resp.status_code} {resp.text[:200]}")
        accept_data = resp.json()
        device_context = accept_data.get("deviceContext")

        # Step 6: Approve authorization
        if device_context and device_context.get("deviceContextId"):
            log.info("[SSO] Step 6: Approving authorization")
            resp = client.post(f"{oidc_base}/device_authorization/associate_token", headers={
                "Content-Type": "application/json",
                "Referer": "https://view.awsapps.com/",
            }, json={
                "deviceContext": {
                    "deviceContextId": device_context["deviceContextId"],
                    "clientId": device_context.get("clientId", client_id),
                    "clientType": device_context.get("clientType", "public"),
                },
                "userSessionId": device_session_token,
            })
            if resp.status_code != 200:
                return _fail(f"Approve failed: {resp.status_code} {resp.text[:200]}")

        # Step 7: Poll for token
        log.info("[SSO] Step 7: Polling for token")
        deadline = time.time() + 120

        while time.time() < deadline:
            time.sleep(interval)
            resp = client.post(f"{oidc_base}/token", json={
                "clientId": client_id,
                "clientSecret": client_secret,
                "grantType": "urn:ietf:params:oauth:grant-type:device_code",
                "deviceCode": device_code,
            })

            if resp.status_code == 200:
                token_data = resp.json()
                log.info("[SSO] Token obtained successfully")
                return {
                    "success": True,
                    "accessToken": token_data["accessToken"],
                    "refreshToken": token_data["refreshToken"],
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "region": region,
                    "expiresIn": token_data.get("expiresIn"),
                }

            if resp.status_code == 400:
                err = resp.json()
                if err.get("error") == "authorization_pending":
                    continue
                if err.get("error") == "slow_down":
                    interval += 5
                    continue
                return _fail(f"Token poll error: {err.get('error')}")

        return _fail("Authorization timeout (120s)")


def _fail(msg: str) -> dict:
    log.error("[SSO] %s", msg)
    return {"success": False, "error": msg}
