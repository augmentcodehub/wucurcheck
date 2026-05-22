"""Kiro Token Refresh: read accounts from KV, refresh OIDC tokens, callback results."""
import json
import os
import sys
import httpx

CF_ACCOUNT_ID = os.environ["CF_ACCOUNT_ID"]
CF_API_TOKEN = os.environ["CF_API_TOKEN"]
KV_NAMESPACE_ID = os.environ["KV_NAMESPACE_ID"]
CALLBACK_URL = os.environ.get("CALLBACK_URL", "")
CALLBACK_SECRET = os.environ.get("CALLBACK_SECRET", "")
TARGET = os.environ.get("TARGET", "")

OIDC_URL = "https://oidc.{region}.amazonaws.com/token"
KV_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{KV_NAMESPACE_ID}"
CF_HEADERS = {"Authorization": f"Bearer {CF_API_TOKEN}"}


def kv_list_accounts(client: httpx.Client) -> list[str]:
    keys = []
    cursor = None
    while True:
        params = {"prefix": "account:"}
        if cursor:
            params["cursor"] = cursor
        r = client.get(f"{KV_BASE}/keys", headers=CF_HEADERS, params=params)
        data = r.json()
        keys.extend(k["name"] for k in data.get("result", []))
        info = data.get("result_info", {})
        if info.get("cursor") and len(data.get("result", [])) > 0:
            cursor = info["cursor"]
        else:
            break
    return keys


def kv_get(client: httpx.Client, key: str) -> dict | None:
    r = client.get(f"{KV_BASE}/values/{key}", headers=CF_HEADERS)
    if r.status_code == 200:
        try:
            return r.json()
        except Exception:
            return None
    return None


def refresh_oidc(client: httpx.Client, account: dict) -> dict:
    rt = account.get("refresh_token", "")
    cid = account.get("client_id", "")
    cs = account.get("client_secret", "")
    region = account.get("region", "us-east-1")

    if not rt or not cid or not cs:
        return {"success": False, "error": "Missing credentials"}

    url = OIDC_URL.replace("{region}", region)
    try:
        r = client.post(url, json={
            "clientId": cid,
            "clientSecret": cs,
            "refreshToken": rt,
            "grantType": "refresh_token",
        }, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return {"success": True, "accessToken": data.get("accessToken"), "refreshToken": data.get("refreshToken", rt), "expiresIn": data.get("expiresIn")}
        else:
            return {"success": False, "error": f"HTTP {r.status_code}: {r.text[:100]}"}
    except Exception as e:
        return {"success": False, "error": str(e)[:100]}


def callback(client: httpx.Client, results: list[dict]):
    if not CALLBACK_URL:
        print("No callback URL, skipping")
        return
    payload = {"secret": CALLBACK_SECRET, "action": "batch_result", "data": {"results": results}}
    r = client.post(CALLBACK_URL, json=payload, timeout=30)
    print(f"Callback: {r.status_code} {r.text[:100]}")


def main():
    with httpx.Client(http2=True) as client:
        if TARGET:
            keys = [f"account:{TARGET}"]
        else:
            keys = kv_list_accounts(client)

        kiro_accounts = []
        for key in keys:
            account = kv_get(client, key)
            if account and account.get("platform") == "kiro" and account.get("refresh_token"):
                kiro_accounts.append(account)

        print(f"Refreshing {len(kiro_accounts)} kiro accounts")
        results = []

        for account in kiro_accounts:
            username = account.get("username", "")
            r = refresh_oidc(client, account)
            if r["success"]:
                results.append({
                    "username": username,
                    "status": "active",
                    "refreshToken": r["refreshToken"],
                    "accessToken": r["accessToken"],
                    "last_result": "Token 刷新成功",
                })
                print(f"  ✓ {username}")
            else:
                results.append({
                    "username": username,
                    "status": "active",
                    "last_result": f"刷新失败: {r['error']}",
                })
                print(f"  ✗ {username}: {r['error']}")

        if results:
            callback(client, results)

        success = sum(1 for r in results if "成功" in r.get("last_result", ""))
        print(f"\nDone: {success}/{len(results)} refreshed")


if __name__ == "__main__":
    main()
