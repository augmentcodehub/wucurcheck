"""Dispatch normalized command requests to command handlers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .request_normalizer import NormalizedCommandRequest


CommandHandler = Callable[[NormalizedCommandRequest], object]


@dataclass(frozen=True)
class CommandDispatchResult:
	success: bool
	payload: dict[str, object]
	error_code: str | None = None


class CommandDispatcher:
	def __init__(
		self,
		*,
		register_handler: CommandHandler,
		list_handler: CommandHandler,
		checkin_handler: CommandHandler,
	):
		self.register_handler = register_handler
		self.list_handler = list_handler
		self.checkin_handler = checkin_handler

	def dispatch(self, request: NormalizedCommandRequest) -> CommandDispatchResult:
		handler = {
			'register': self.register_handler,
			'list': self.list_handler,
			'checkin': self.checkin_handler,
		}.get(request.command)

		if handler is None:
			return CommandDispatchResult(False, {}, 'INVALID_COMMAND')

		try:
			raw_result = handler(request)
		except Exception as exc:
			return CommandDispatchResult(False, {'message': str(exc)}, 'HANDLER_FAILED')

		return _coerce_result(raw_result)


def _coerce_result(result: object) -> CommandDispatchResult:
	if isinstance(result, CommandDispatchResult):
		return result

	if isinstance(result, int):
		return CommandDispatchResult(result == 0, {'exit_code': result}, None if result == 0 else 'HANDLER_FAILED')

	if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], bool) and isinstance(result[1], dict):
		return CommandDispatchResult(result[0], result[1], None)

	if isinstance(result, dict):
		success_value = result.get('success')
		if isinstance(success_value, bool):
			success = success_value
		else:
			success = True
		error_code = result.get('error_code')
		if error_code is not None and not isinstance(error_code, str):
			error_code = str(error_code)
		return CommandDispatchResult(success, result, error_code if isinstance(error_code, str) else None)

	return CommandDispatchResult(True, {'result': result})
