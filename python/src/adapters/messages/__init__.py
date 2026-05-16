"""Message ingress adapters."""

from .feishu import handle_message as handle_feishu_message
from .telegram import handle_message as handle_telegram_message

__all__ = ['handle_feishu_message', 'handle_telegram_message']
