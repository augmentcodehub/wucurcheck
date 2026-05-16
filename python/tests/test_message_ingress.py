from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from adapters.messages.feishu import handle_message as handle_feishu_message
from adapters.messages.telegram import handle_message as handle_telegram_message


@dataclass
class DummyDispatcher:
	result: object
	last_request: object = None

	def dispatch(self, request):
		self.last_request = request
		return self.result


def test_feishu_message_normalizes_and_dispatches():
	dispatcher = DummyDispatcher(result={'success': True})

	result = handle_feishu_message({'command': 'list', 'provider': 'wucur', 'backend': 'sqlite'}, dispatcher)

	assert result == {'success': True}
	assert dispatcher.last_request.command == 'list'


def test_telegram_message_normalizes_and_dispatches():
	dispatcher = DummyDispatcher(result={'success': True})

	result = handle_telegram_message({'command': 'checkin', 'provider': 'wucur', 'backend': 'sqlite'}, dispatcher)

	assert result == {'success': True}
	assert dispatcher.last_request.command == 'checkin'
