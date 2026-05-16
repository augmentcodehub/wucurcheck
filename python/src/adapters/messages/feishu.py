"""Feishu message ingress adapter."""

from __future__ import annotations

from core.application.command_dispatcher import CommandDispatcher
from core.application.request_normalizer import normalize_command_request


def handle_message(payload: dict, dispatcher: CommandDispatcher):
	request = normalize_command_request(payload)
	return dispatcher.dispatch(request)
