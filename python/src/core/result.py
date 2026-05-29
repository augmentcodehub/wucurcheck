"""Unified Result value object."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    success: bool
    data: dict | None = None
    message: str = ""

    @classmethod
    def ok(cls, data: dict | None = None, message: str = "") -> Result:
        return cls(success=True, data=data, message=message)

    @classmethod
    def fail(cls, message: str, data: dict | None = None) -> Result:
        return cls(success=False, data=data, message=message)
