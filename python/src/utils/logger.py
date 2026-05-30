"""Structured logger — delegates to pycore.

Keeps the same import path so existing code doesn't break:
    from utils.logger import get_logger
"""

from pycore.log import logger as get_logger  # noqa: F401
