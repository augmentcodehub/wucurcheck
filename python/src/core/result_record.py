"""Typed output record for results.json — the unified CLI output contract."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ResultRecord:
	"""Single account result in results.json. Only non-None fields are serialized."""

	username: str
	status: str = 'active'
	last_result: str = ''
	platform: Optional[str] = None
	password: Optional[str] = None
	balance: Optional[str] = None
	checkin_time: Optional[str] = None
	register_source: Optional[str] = None
	refreshToken: Optional[str] = None
	accessToken: Optional[str] = None

	def to_dict(self) -> dict:
		"""Serialize, omitting None values."""
		return {k: v for k, v in asdict(self).items() if v is not None}
