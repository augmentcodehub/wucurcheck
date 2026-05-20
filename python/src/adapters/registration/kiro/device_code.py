"""Obtain a device code for constructing the Kiro registration URL."""

from __future__ import annotations

import logging

import httpx

from .constants import OIDC_BASE, SCOPES, START_URL

log = logging.getLogger(__name__)


def obtain_device_code() -> dict[str, str] | None:
    """Register an OIDC client and obtain a user_code for the device flow.

    Returns:
        {"user_code": "..."} on success, None on failure.
    """
    try:
        resp = httpx.post(
            f"{OIDC_BASE}/client/register",
            json={
                "clientName": "Kiro Account Manager",
                "clientType": "public",
                "scopes": SCOPES,
                "grantTypes": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
                "issuerUrl": START_URL,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            log.error("OIDC client register failed: %d %s", resp.status_code, resp.text[:200])
            return None
        reg = resp.json()

        resp = httpx.post(
            f"{OIDC_BASE}/device_authorization",
            json={
                "clientId": reg["clientId"],
                "clientSecret": reg["clientSecret"],
                "startUrl": START_URL,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            log.error("Device authorization failed: %d %s", resp.status_code, resp.text[:200])
            return None

        dev = resp.json()
        return {"user_code": dev["userCode"]}

    except httpx.HTTPError as exc:
        log.error("HTTP error obtaining device code: %s", exc)
        return None
