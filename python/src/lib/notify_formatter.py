"""签到通知格式化。"""
from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class CheckinDetail(TypedDict):
	"""签到前后余额变化详情。"""

	name: str
	before_quota: float
	before_used: float
	after_quota: float
	after_used: float
	check_in_reward: float
	usage_increase: float
	balance_change: float


def format_check_in_notification(detail: CheckinDetail) -> str:
	"""格式化单个账号的签到通知消息。"""
	lines = [
		f'[CHECK-IN] {detail["name"]}',
		'  ━━━━━━━━━━━━━━━━━━━━',
		'  📍 签到前',
		f'     💵 余额: ${detail["before_quota"]:.2f}  |  📊 累计消耗: ${detail["before_used"]:.2f}',
		'  📍 签到后',
		f'     💵 余额: ${detail["after_quota"]:.2f}  |  📊 累计消耗: ${detail["after_used"]:.2f}',
	]

	# 判断是否有变化
	has_reward = detail['check_in_reward'] != 0
	has_usage = detail['usage_increase'] != 0

	if has_reward or has_usage:
		lines.append('  ━━━━━━━━━━━━━━━━━━━━')

		# 已签到但期间有使用
		if not has_reward and has_usage:
			lines.append('  ℹ️  今日已签到（期间有使用）')

		# 签到获得
		if has_reward:
			lines.append(f'  🎁 签到获得: +${detail["check_in_reward"]:.2f}')

		# 期间消耗
		if has_usage:
			lines.append(f'  📉 期间消耗: ${detail["usage_increase"]:.2f}')

		# 余额变化
		if detail['balance_change'] != 0:
			change_symbol = '+' if detail['balance_change'] > 0 else ''
			change_emoji = '📈' if detail['balance_change'] > 0 else '📉'
			lines.append(f'  {change_emoji} 余额变化: {change_symbol}${detail["balance_change"]:.2f}')
	else:
		# 无任何变化
		lines.extend(['  ━━━━━━━━━━━━━━━━━━━━', '  ℹ️  今日已签到，无变化'])

	return '\n'.join(lines)


def format_batch_summary(success_count: int, total_count: int) -> str:
	"""格式化批量签到汇总（新增辅助函数，cli/checkin.py 当前不调用）。"""
	lines = [
		'[STATS] Check-in result statistics:',
		f'[SUCCESS] Success: {success_count}/{total_count}',
		f'[FAIL] Failed: {total_count - success_count}/{total_count}',
	]
	if success_count == total_count:
		lines.append('[SUCCESS] All accounts check-in successful!')
	elif success_count > 0:
		lines.append('[WARN] Some accounts check-in successful')
	else:
		lines.append('[ERROR] All accounts check-in failed')

	time_info = f'[TIME] Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
	return '\n'.join([time_info] + lines)
