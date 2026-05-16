"""GitHub workflow dispatch port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class GitHubDispatchPort(Protocol):
	def dispatch(self, action: str, target: str | None, callback_url: str | None) -> dict[str, object]:
		...
