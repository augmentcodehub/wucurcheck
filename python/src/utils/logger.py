"""Shared structured logger for CLI entrypoints."""

from __future__ import annotations

import json
import logging
import sys


_INITIALIZED = False
_STANDARD_ATTRS = {
	'name',
	'msg',
	'args',
	'levelname',
	'levelno',
	'pathname',
	'filename',
	'module',
	'exc_info',
	'exc_text',
	'stack_info',
	'lineno',
	'funcName',
	'created',
	'msecs',
	'relativeCreated',
	'thread',
	'threadName',
	'processName',
	'process',
}


class JsonFormatter(logging.Formatter):
	def format(self, record: logging.LogRecord) -> str:
		entry = {
			'ts': round(record.created, 3),
			'level': record.levelname.lower(),
			'module': record.name.removeprefix('anyrouter.'),
			'msg': record.getMessage(),
		}
		for key, value in record.__dict__.items():
			if key not in _STANDARD_ATTRS and not key.startswith('_'):
				entry[key] = value
		return json.dumps(entry, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
	global _INITIALIZED

	logger = logging.getLogger(f'anyrouter.{name}')
	if not _INITIALIZED:
		handler = logging.StreamHandler(sys.stderr)
		handler.setFormatter(JsonFormatter())

		root = logging.getLogger('anyrouter')
		root.addHandler(handler)
		root.setLevel(logging.INFO)
		root.propagate = False
		_INITIALIZED = True

	return logger
