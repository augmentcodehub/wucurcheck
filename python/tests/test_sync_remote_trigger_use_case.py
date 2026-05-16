from __future__ import annotations

from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.application.sync_remote_trigger_use_case import SyncRemoteTriggerUseCase


class DummyDispatchPort:
	def __init__(self, result: dict[str, object]):
		self.result = result
		self.calls: list[tuple[str, str | None, str | None]] = []

	def dispatch(self, action: str, target: str | None, callback_url: str | None) -> dict[str, object]:
		self.calls.append((action, target, callback_url))
		return self.result


def test_sync_remote_trigger_defaults_to_checkin():
	port = DummyDispatchPort({'ok': True, 'dispatch_id': 'dispatch-1'})
	use_case = SyncRemoteTriggerUseCase(port)

	result = use_case.run(target='alice')

	assert result.success is True
	assert result.workflow == 'checkin'
	assert result.defaulted is True
	assert result.dispatch_id == 'dispatch-1'
	assert port.calls == [('checkin', 'alice', None)]


def test_sync_remote_trigger_propagates_dispatch_failure():
	port = DummyDispatchPort({'ok': False})
	use_case = SyncRemoteTriggerUseCase(port)

	result = use_case.run(workflow='checkin', target='alice')

	assert result.success is False
	assert result.error_code == 'DISPATCH_FAILED'


def test_sync_remote_trigger_uses_explicit_workflow():
	port = DummyDispatchPort({'ok': True, 'workflow': 'custom', 'defaulted': False, 'dispatch_id': 'dispatch-2'})
	use_case = SyncRemoteTriggerUseCase(port)

	result = use_case.run(action='checkin', target='alice', workflow='custom')

	assert result.workflow == 'custom'
	assert result.defaulted is False
	assert result.dispatch_id == 'dispatch-2'
	assert port.calls == [('checkin', 'alice', None)]
