"""Check if Kiro trial was activated for an account."""
import sys
import json
import cbor2
import httpx

token = sys.argv[1]
resp = httpx.post(
    "https://app.kiro.dev/service/KiroWebPortalService/operation/GetUserUsageAndLimits",
    headers={
        "accept": "application/cbor",
        "content-type": "application/cbor",
        "smithy-protocol": "rpc-v2-cbor",
        "authorization": f"Bearer {token}",
        "cookie": f"Idp=BuilderId; AccessToken={token}",
    },
    content=cbor2.dumps({"isEmailRequired": True, "origin": "KIRO_IDE"}),
    timeout=30,
)
if resp.status_code == 200:
    data = cbor2.loads(resp.content)
    credit = next((b for b in data.get("usageBreakdownList", []) if b.get("resourceType") == "CREDIT"), {})
    ft = credit.get("freeTrialInfo")
    limit = credit.get("usageLimit", 0)
    bonuses = credit.get("bonuses", [])
    total = limit + (ft.get("usageLimit", 0) if ft else 0) + sum(b.get("usageLimit", 0) for b in bonuses)
    print(json.dumps({"base_limit": limit, "free_trial": ft.get("usageLimit", 0) if ft else 0, "total_limit": total, "activated": total > limit}))
else:
    print(json.dumps({"error": f"HTTP {resp.status_code}", "activated": False}))
