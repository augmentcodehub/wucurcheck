"""共享常量。"""

QUOTA_UNIT_DIVISOR = 500_000
"""wucur API 返回的 quota 原始值除以此数得到美元金额。"""

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

DEFAULT_PASSWORD = "123Claude&Codex"
"""KV 中缺少 password 字段时的 fallback。"""
