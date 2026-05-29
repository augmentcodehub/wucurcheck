"""HTTP 工具函数 — 不创建 Client，只提供辅助方法。Client 由调用方管理。"""
import json as _json

import httpx

from lib.constants import DEFAULT_USER_AGENT


def parse_response(resp: httpx.Response) -> dict:
    """安全解析 JSON 响应。"""
    try:
        return resp.json()
    except (_json.JSONDecodeError, Exception):
        return {"success": False, "message": f"HTTP {resp.status_code}: invalid JSON"}


def build_headers(origin: str, referer_path: str) -> dict[str, str]:
    """构建标准登录/API 请求头。"""
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": origin,
        "Referer": f"{origin}{referer_path}",
    }
