from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.application.command_dispatcher import CommandDispatcher
from core.application.request_normalizer import NormalizedCommandRequest


@dataclass
class DummyHandler:
	result: object
	calls: list[NormalizedCommandRequest]

	def __call__(self, request: NormalizedCommandRequest):
		self.calls.append(request)
		return self.result


def test_dispatch_register_routes_to_register_handler():
	handler = DummyHandler({'success': True}, [])
	dispatcher = CommandDispatcher(register_handler=handler, list_handler=handler, checkin_handler=handler)

	result = dispatcher.dispatch(
		NormalizedCommandRequest(command='register', provider='wucur', backend='sqlite', account={'name': 'a', 'username': 'b', 'password': 'c'})
	)

	assert result.success is True
	assert handler.calls[0].command == 'register'


def test_dispatch_list_routes_to_list_handler():
	handler = DummyHandler({'success': True}, [])
	dispatcher = CommandDispatcher(register_handler=handler, list_handler=handler, checkin_handler=handler)

	result = dispatcher.dispatch(NormalizedCommandRequest(command='list', provider='wucur', backend='sqlite'))

	assert result.success is True
	assert handler.calls[0].command == 'list'

