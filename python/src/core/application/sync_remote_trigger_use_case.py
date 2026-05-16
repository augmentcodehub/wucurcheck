"""Application use case for worker-triggered GitHub workflow dispatch."""

from __future__ import annotations

from dataclasses import dataclass

from core.ports.github_dispatch import GitHubDispatchPort


@dataclass(frozen=True)
class SyncRemoteTriggerResult:
	success: bool
	workflow: str | None = None
	defaulted: bool = False
	dispatch_id: str | None = None
	error_code: str | None = None


class SyncRemoteTriggerUseCase:
	def __init__(self, dispatch_port: GitHubDispatchPort):
		self.dispatch_port = dispatch_port

	def run(
		self,
		*,
		action: str = 'checkin',
		target: str | None = None,
		callback_url: str | None = None,
		workflow: str | None = None,
	) -> SyncRemoteTriggerResult:
		workflow_name = (workflow or 'checkin').strip() or 'checkin'
		defaulted = not workflow or not workflow.strip()

		result = self.dispatch_port.dispatch(action, target, callback_url)
		if not result.get('ok'):
			return SyncRemoteTriggerResult(False, workflow_name, defaulted, None, 'DISPATCH_FAILED')

		return SyncRemoteTriggerResult(
			True,
			str(result.get('workflow') or workflow_name),
			bool(result.get('defaulted', defaulted)),
			str(result.get('dispatch_id')) if result.get('dispatch_id') is not None else None,
			None,
		)
