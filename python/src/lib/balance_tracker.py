"""余额变化追踪 — 通过 hash 比较判断是否需要发通知。"""
import hashlib
import json
import os

from utils.logger import get_logger

log = get_logger("lib.balance_tracker")

BALANCE_HASH_FILE = "balance_hash.txt"


def load_balance_hash() -> str | None:
	"""加载余额hash"""
	try:
		if os.path.exists(BALANCE_HASH_FILE):
			with open(BALANCE_HASH_FILE, 'r', encoding='utf-8') as f:
				return f.read().strip()
	except Exception:  # nosec B110
		pass
	return None


def save_balance_hash(balance_hash: str) -> None:
	"""保存余额hash"""
	try:
		with open(BALANCE_HASH_FILE, 'w', encoding='utf-8') as f:
			f.write(balance_hash)
	except Exception as e:
		log.warning('Failed to save balance hash', extra={'error': str(e)})


def generate_balance_hash(balances: dict[str, dict]) -> str | None:
	"""生成余额数据的hash"""
	# 将包含 quota 和 used 的结构转换为简单的 quota 值用于 hash 计算
	simple_balances = {k: v['quota'] for k, v in balances.items()} if balances else {}
	if not simple_balances:
		return None
	balance_json = json.dumps(simple_balances, sort_keys=True, separators=(',', ':'))
	return hashlib.sha256(balance_json.encode('utf-8')).hexdigest()[:16]


def has_balance_changed(current_balances: dict[str, dict]) -> bool:
	"""比较当前余额和上次保存的 hash，返回是否有变化。同时保存新 hash。

	注意：此函数有副作用（写文件）。拆分为 detect + save 两步供需要纯判断的场景使用。
	"""
	changed = detect_balance_change(current_balances)
	current_hash = generate_balance_hash(current_balances)
	if current_hash:
		save_balance_hash(current_hash)
	return changed


def detect_balance_change(current_balances: dict[str, dict]) -> bool:
	"""纯判断：当前余额是否和上次不同。无副作用。"""
	current_hash = generate_balance_hash(current_balances)
	if not current_hash:
		return False
	last_hash = load_balance_hash()
	return last_hash is None or current_hash != last_hash
