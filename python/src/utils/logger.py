"""Shared structured logger for CLI entrypoints.

Usage:
    from utils.logger import get_logger
    log = get_logger("module.name")

    # kwargs style (preferred)
    log.info("Login success", username=username, provider="wucur")

    # extra= style (legacy, still works)
    log.info("Login success", extra={"username": username})
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


_INITIALIZED = False
_STANDARD_ATTRS = {
	'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
	'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
	'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
	'processName', 'process', 'taskName',
}

_LOG_KWARGS = {'exc_info', 'stack_info', 'stacklevel', 'extra'}


class _JsonFormatter(logging.Formatter):
	def format(self, record: logging.LogRecord) -> str:
		entry: dict[str, Any] = {
			'ts': round(record.created, 3),
			'level': record.levelname.lower(),
			'module': record.name.removeprefix('anyrouter.'),
			'msg': record.getMessage(),
		}
		for key, value in record.__dict__.items():
			if key.startswith('_extra_'):
				entry[key[7:]] = value
			elif key not in _STANDARD_ATTRS and not key.startswith('_'):
				entry[key] = value
		return json.dumps(entry, ensure_ascii=False)


class _LoggerAdapter(logging.LoggerAdapter):
	"""Adapter that accepts kwargs as structured fields."""

	def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
		extra = kwargs.get('extra', {})
		for k, v in list(kwargs.items()):
			if k not in _LOG_KWARGS:
				extra[f'_extra_{k}'] = v
		kwargs = {k: v for k, v in kwargs.items() if k in _LOG_KWARGS}
		kwargs['extra'] = extra
		return msg, kwargs


def get_logger(name: str) -> _LoggerAdapter:
	"""Get a structured logger. Accepts kwargs as structured fields.

	    log.info("msg", key=val)  →  {"ts":...,"msg":"msg","key":"val"}
	"""
	global _INITIALIZED
	if not _INITIALIZED:
		handler = logging.StreamHandler(sys.stderr)
		handler.setFormatter(_JsonFormatter())
		root = logging.getLogger('anyrouter')
		root.addHandler(handler)
		root.setLevel(logging.INFO)
		root.propagate = False
		_INITIALIZED = True

	return _LoggerAdapter(logging.getLogger(f'anyrouter.{name}'), {})
