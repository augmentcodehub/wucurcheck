"""Simple typed registry for providers/pipelines."""
from __future__ import annotations

from typing import Any


class Registry:
    """A registry that stores singleton instances by name."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, Any] = {}

    def register(self, cls: type) -> type:
        """Decorator to register a class (instantiates immediately)."""
        instance = cls()
        name = getattr(instance, "name", cls.__name__)
        self._items[name] = instance
        return cls

    def get(self, name: str) -> Any | None:
        return self._items.get(name)
