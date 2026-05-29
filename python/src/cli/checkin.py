#!/usr/bin/env python3
"""
AnyRouter.top 自动签到脚本
"""

import asyncio
import json
import os
import sys
from datetime import datetime

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from utils.config import AccountConfig, AppConfig, load_accounts_config
from utils.logger import get_logger
from utils.notify import notify
from lib.balance_tracker import load_balance_hash, save_balance_hash, generate_balance_hash
from lib.notify_formatter import format_check_in_notification

log = get_logger('cli.checkin')

load_dotenv()

try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


def parse_cookies(cookies_data):
	"""解析 cookies 数据"""
	if cookies_data is None:
		return {}

	if isinstance(cookies_data, dict):
		return cookies_data

	if isinstance(cookies_data, str):
		cookies_dict = {}
		for cookie in cookies_data.split(';'):
			if '=' in cookie:
				key, value = cookie.strip().split('=', 1)
				cookies_dict[key] = value
		return cookies_dict
	return {}


def build_login_payload(account: AccountConfig) -> dict:
	"""构造登录请求体"""
	return {
		'username': account.username,
		'password': account.password,
	}


def extract_token_from_login_response(response: httpx.Response) -> str | None:
	"""从登录响应中提取 Bearer token"""
	try:
		data = response.json()
	except json.JSONDecodeError:
		return None

	if not isinstance(data, dict):
		return None

	user_data = data.get('user')
	if isinstance(user_data, dict):
		token = user_data.get('token')
		if isinstance(token, str) and token.strip():
			return token.strip()

	data_node = data.get('data')
	if isinstance(data_node, dict):
		user_data = data_node.get('user')
		if isinstance(user_data, dict):
			token = user_data.get('token')
			if isinstance(token, str) and token.strip():
				return token.strip()

	return None


def extract_login_user_id(response: httpx.Response) -> str | None:
	"""从登录响应中提取用户 ID"""
	try:
		data = response.json()
	except json.JSONDecodeError:
		return None

	if not isinstance(data, dict):
		return None

	data_node = data.get('data')
	if isinstance(data_node, dict):
		user_id = data_node.get('id')
		if user_id is not None:
			return str(user_id)

	user_data = data.get('user')
	if isinstance(user_data, dict):
		user_id = user_data.get('id')
		if user_id is not None:
			return str(user_id)

	return None


async def get_waf_cookies_with_playwright(account_name: str, login_url: str, required_cookies: list[str]):
	"""使用 Playwright 获取 WAF cookies（隐私模式）"""
	log.info('Starting browser to get WAF cookies...', extra={'account': account_name})

	async with async_playwright() as p:
		import tempfile

		with tempfile.TemporaryDirectory() as temp_dir:
			context = await p.chromium.launch_persistent_context(
				user_data_dir=temp_dir,
				headless=False,
				user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
				viewport={'width': 1920, 'height': 1080},
				args=[
					'--disable-blink-features=AutomationControlled',
					'--disable-dev-shm-usage',
					'--disable-web-security',
					'--disable-features=VizDisplayCompositor',
					'--no-sandbox',
				],
			)

			page = await context.new_page()

			try:
				log.info('Access login page to get initial cookies...', extra={'account': account_name})

				await page.goto(login_url, wait_until='networkidle')

				try:
					await page.wait_for_function('document.readyState === "complete"', timeout=5000)
				except Exception:
					await page.wait_for_timeout(3000)

				cookies = await page.context.cookies()

				waf_cookies = {}
				for cookie in cookies:
					cookie_name = cookie.get('name')
					cookie_value = cookie.get('value')
					if cookie_name in required_cookies and cookie_value is not None:
						waf_cookies[cookie_name] = cookie_value

				log.info('Got {len(waf_cookies)} WAF cookies', extra={'account': account_name})

				missing_cookies = [c for c in required_cookies if c not in waf_cookies]

				if missing_cookies:
					log.error('Missing WAF cookies: {missing_cookies}', extra={'account': account_name})
					await context.close()
					return None

				log.info('Successfully got all WAF cookies', extra={'account': account_name})

				await context.close()

				return waf_cookies

			except Exception as e:
				log.error('Error occurred while getting WAF cookies: ', extra={'account': account_name, 'error': str(e)})
				await context.close()
				return None


def get_user_info(client, headers, user_info_url: str):
	"""获取用户信息"""
	try:
		response = client.get(user_info_url, headers=headers, timeout=30)

		if response.status_code == 200:
			data = response.json()
			if data.get('success'):
				user_data = data.get('data', {})
				quota = round(user_data.get('quota', 0) / 500000, 2)
				used_quota = round(user_data.get('used_quota', 0) / 500000, 2)
				return {
					'success': True,
					'quota': quota,
					'used_quota': used_quota,
					'display': f':money: Current balance: ${quota}, Used: ${used_quota}',
				}
		return {'success': False, 'error': f'Failed to get user info: HTTP {response.status_code}'}
	except Exception as e:
		return {'success': False, 'error': f'Failed to get user info: {str(e)[:50]}...'}


def login_with_bearer_token(client: httpx.Client, account_name: str, provider_config, account: AccountConfig) -> str | None:
	"""通过账号密码登录并提取 Bearer token"""
	if not account.username or not account.password:
		log.error('Missing username/password for bearer login', extra={'account': account_name})
		return None

	if not provider_config.login_api_path:
		log.error('Provider "{provider_config.name}" missing login_api_path', extra={'account': account_name})
		return None

	login_headers = {
		'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
		'Accept': 'application/json, text/plain, */*',
		'Content-Type': 'application/json',
		'Origin': provider_config.domain,
		'Referer': f'{provider_config.domain}{provider_config.login_path}',
	}
	login_url = f'{provider_config.domain}{provider_config.login_api_path}'

	try:
		response = client.post(login_url, headers=login_headers, json=build_login_payload(account), timeout=30)
	except Exception as e:
		log.error('Login request failed', extra={'account': account_name, 'error': str(e)[:50]})
		return None

	if response.status_code != 200:
		log.error('Login failed', extra={'account': account_name, 'status': response.status_code})
		return None

	token = extract_token_from_login_response(response)
	if not token:
		log.error('Login succeeded but token was not found', extra={'account': account_name})
		return None

	log.info('Bearer token acquired', extra={'account': account_name})
	return token


def login_with_session(client: httpx.Client, account_name: str, provider_config, account: AccountConfig) -> str | None:
	"""通过账号密码登录并复用服务端设置的 session cookie"""
	if not account.username or not account.password:
		log.error('Missing username/password for password session login', extra={'account': account_name})
		return None

	if not provider_config.login_api_path:
		log.error('Provider "{provider_config.name}" missing login_api_path', extra={'account': account_name})
		return None

	login_headers = {
		'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
		'Accept': 'application/json, text/plain, */*',
		'Content-Type': 'application/json',
		'Origin': provider_config.domain,
		'Referer': f'{provider_config.domain}{provider_config.login_path}',
	}
	login_url = f'{provider_config.domain}{provider_config.login_api_path}'

	try:
		response = client.post(login_url, headers=login_headers, json=build_login_payload(account), timeout=30)
	except Exception as e:
		log.error('Login request failed', extra={'account': account_name, 'error': str(e)[:50]})
		return None

	if response.status_code != 200:
		log.error('Login failed', extra={'account': account_name, 'status': response.status_code})
		return None

	try:
		result = response.json()
	except json.JSONDecodeError:
		log.error('Login failed - invalid JSON response', extra={'account': account_name})
		return None

	if not result.get('success'):
		error_msg = result.get('message', 'Unknown error')
		log.error('Login failed', extra={'account': account_name, 'error_msg': error_msg})
		return None

	if 'session' not in client.cookies:
		log.error('Login succeeded but session cookie was not found', extra={'account': account_name})
		return None

	user_id = extract_login_user_id(response)
	log.info('Session login successful', extra={'account': account_name})
	return user_id


async def prepare_cookies(account_name: str, provider_config, user_cookies: dict) -> dict | None:
	"""准备请求所需的 cookies（可能包含 WAF cookies）"""
	waf_cookies = {}

	if provider_config.needs_waf_cookies():
		login_url = f'{provider_config.domain}{provider_config.login_path}'
		waf_cookies = await get_waf_cookies_with_playwright(account_name, login_url, provider_config.waf_cookie_names)
		if not waf_cookies:
			log.error('Unable to get WAF cookies', extra={'account': account_name})
			return None
	else:
		log.info('Bypass WAF not required, using user cookies directly', extra={'account': account_name})

	return {**waf_cookies, **user_cookies}


def execute_check_in(client, account_name: str, provider_config, headers: dict):
	"""执行签到请求"""
	log.info('Executing check-in', extra={'account': account_name})

	checkin_headers = headers.copy()
	checkin_headers.update({'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})

	sign_in_url = f'{provider_config.domain}{provider_config.sign_in_path}'
	response = client.post(sign_in_url, headers=checkin_headers, timeout=30)

	log.info('Response status code', extra={'account': account_name, 'status': response.status_code})

	if response.status_code == 200:
		try:
			result = response.json()
			if result.get('ret') == 1 or result.get('code') == 0 or result.get('success'):
				log.info('Check-in successful!', extra={'account': account_name})
				return True
			else:
				error_msg = result.get('msg', result.get('message', 'Unknown error'))
				# 检查是否是"已经签到过"的情况，这种情况也算成功
				already_checked_keywords = ['已经签到', '已签到', '重复签到', 'already checked', 'already signed']
				if any(keyword in error_msg.lower() for keyword in already_checked_keywords):
					log.info('Already checked in today', extra={'account': account_name})
					return True
				log.error('Check-in failed', extra={'account': account_name, 'error_msg': error_msg})
				return False
		except json.JSONDecodeError:
			# 如果不是 JSON 响应，检查是否包含成功标识
			if 'success' in response.text.lower():
				log.info('Check-in successful!', extra={'account': account_name})
				return True
			else:
				log.error('Check-in failed - Invalid response format', extra={'account': account_name})
				return False
	else:
		log.error('Check-in failed', extra={'account': account_name, 'status': response.status_code})
		return False


async def check_in_account(account: AccountConfig, account_index: int, app_config: AppConfig):
	"""为单个账号执行签到操作"""
	account_name = account.get_display_name(account_index)
	log.info('Processing account', extra={'account': account_name})

	provider_config = app_config.get_provider(account.provider)
	if not provider_config:
		log.error('Provider "{account.provider}" not found in configuration', extra={'account': account_name})
		return False, None, None

	log.info('Using provider "{account.provider}" ({provider_config.domain})', extra={'account': account_name})

	user_cookies = parse_cookies(account.cookies)
	if not provider_config.uses_bearer_login() and not provider_config.uses_password_session() and not user_cookies:
		log.error('Invalid configuration format', extra={'account': account_name})
		return False, None, None

	client = httpx.Client(http2=True, timeout=30.0)

	try:
		if provider_config.uses_bearer_login():
			token = login_with_bearer_token(client, account_name, provider_config, account)
			if not token:
				return False, None, None
			logged_in_api_user = None
		elif provider_config.uses_password_session():
			logged_in_api_user = login_with_session(client, account_name, provider_config, account)
			if not logged_in_api_user:
				return False, None, None
			token = None
		else:
			all_cookies = await prepare_cookies(account_name, provider_config, user_cookies)
			if not all_cookies:
				return False, None, None
			client.cookies.update(all_cookies)
			token = None
			logged_in_api_user = account.api_user

		headers = {
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
			'Accept': 'application/json, text/plain, */*',
			'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
			'Accept-Encoding': 'gzip, deflate, br, zstd',
			'Referer': provider_config.domain,
			'Origin': provider_config.domain,
			'Connection': 'keep-alive',
			'Sec-Fetch-Dest': 'empty',
			'Sec-Fetch-Mode': 'cors',
			'Sec-Fetch-Site': 'same-origin',
		}
		api_user_value = account.api_user or logged_in_api_user
		if provider_config.api_user_key and api_user_value:
			headers[provider_config.api_user_key] = api_user_value
		if token:
			headers['Authorization'] = f'Bearer {token}'

		user_info_before = None
		user_info_after = None
		user_info_url = None
		if provider_config.user_info_path:
			user_info_url = f'{provider_config.domain}{provider_config.user_info_path}'
			user_info_before = get_user_info(client, headers, user_info_url)
			if user_info_before and user_info_before.get('success'):
				log.info('User info', extra={'account': account_name, 'display': user_info_before['display']})
			elif user_info_before:
				log.warning('User info error', extra={'account': account_name, 'error': user_info_before.get('error', 'Unknown error')})

		if provider_config.needs_manual_check_in():
			success = execute_check_in(client, account_name, provider_config, headers)
			# 签到后再次获取用户信息，用于计算签到收益
			if user_info_url:
				user_info_after = get_user_info(client, headers, user_info_url)
			return success, user_info_before, user_info_after
		else:
			log.info('Check-in completed automatically (triggered by user info request)', extra={'account': account_name})
			# 自动签到的情况，再次获取用户信息
			if user_info_url:
				user_info_after = get_user_info(client, headers, user_info_url)
			return True, user_info_before, user_info_after

	except Exception as e:
		log.error('Error occurred during check-in process', extra={'account': account_name, 'error': str(e)[:50]})
		return False, None, None
	finally:
		client.close()


async def main():
	"""主函数"""
	log.info('Checkin script started')
	log.info('Execution started', extra={'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

	app_config = AppConfig.load_from_env()
	log.info('Providers loaded', extra={'count': len(app_config.providers)})

	accounts = load_accounts_config()
	if not accounts:
		log.error('Unable to load account configuration')
		sys.exit(1)

	log.info('Accounts loaded', extra={'count': len(accounts)})

	last_balance_hash = load_balance_hash()

	success_count = 0
	total_count = len(accounts)
	notification_content = []
	current_balances = {}
	account_check_in_details = {}  # 存储每个账号的签到详情
	need_notify = False  # 是否需要发送通知
	balance_changed = False  # 余额是否有变化

	for i, account in enumerate(accounts):
		account_key = f'account_{i + 1}'
		try:
			success, user_info_before, user_info_after = await check_in_account(account, i, app_config)
			if success:
				success_count += 1

			should_notify_this_account = False

			if not success:
				should_notify_this_account = True
				need_notify = True
				account_name = account.get_display_name(i)
				log.info('Account failed, will notify', extra={'account': account_name})

			# 存储签到前后的余额信息
			if user_info_after and user_info_after.get('success'):
				current_quota = user_info_after['quota']
				current_used = user_info_after['used_quota']
				current_balances[account_key] = {'quota': current_quota, 'used': current_used}

				# 计算签到收益
				if user_info_before and user_info_before.get('success'):
					before_quota = user_info_before['quota']
					before_used = user_info_before['used_quota']
					after_quota = user_info_after['quota']
					after_used = user_info_after['used_quota']

					# 计算总额度（余额 + 历史消耗）
					total_before = before_quota + before_used
					total_after = after_quota + after_used

					# 签到获得的额度 = 总额度增加量
					check_in_reward = total_after - total_before

					# 本次消耗 = 历史消耗增加量
					usage_increase = after_used - before_used

					# 余额变化
					balance_change = after_quota - before_quota

					account_check_in_details[account_key] = {
						'name': account.get_display_name(i),
						'before_quota': before_quota,
						'before_used': before_used,
						'after_quota': after_quota,
						'after_used': after_used,
						'check_in_reward': check_in_reward,  # 签到获得
						'usage_increase': usage_increase,  # 本次消耗
						'balance_change': balance_change,  # 余额变化
						'success': success,
					}

			if should_notify_this_account:
				account_name = account.get_display_name(i)
				status = '[SUCCESS]' if success else '[FAIL]'
				account_result = f'{status} {account_name}'
				if user_info_after and user_info_after.get('success'):
					account_result += f'\n{user_info_after["display"]}'
				elif user_info_after:
					account_result += f'\n{user_info_after.get("error", "Unknown error")}'
				notification_content.append(account_result)

		except Exception as e:
			account_name = account.get_display_name(i)
			log.error('Processing exception', extra={'account': account_name, 'error': str(e)})
			need_notify = True  # 异常也需要通知
			notification_content.append(f'[FAIL] {account_name} exception: {str(e)[:50]}...')

	# 检查余额变化
	current_balance_hash = generate_balance_hash(current_balances) if current_balances else None
	if current_balance_hash:
		if last_balance_hash is None:
			# 首次运行
			balance_changed = True
			need_notify = True
			log.info('First run detected, will send notification with current balances')
		elif current_balance_hash != last_balance_hash:
			# 余额有变化
			balance_changed = True
			need_notify = True
			log.info('Balance changes detected, will send notification')
		else:
			log.info('No balance changes detected')

	# 为有余额变化的情况添加所有成功账号到通知内容
	if balance_changed:
		for i, account in enumerate(accounts):
			account_key = f'account_{i + 1}'
			if account_key in account_check_in_details:
				detail = account_check_in_details[account_key]
				account_name = detail['name']

				# 使用格式化函数生成通知消息
				account_result = format_check_in_notification(detail)

				# 检查是否已经在通知内容中（避免重复）
				if not any(account_name in item for item in notification_content):
					notification_content.append(account_result)

	# 保存当前余额hash
	if current_balance_hash:
		save_balance_hash(current_balance_hash)

	if need_notify and notification_content:
		# 构建通知内容
		summary = [
			'[STATS] Check-in result statistics:',
			f'[SUCCESS] Success: {success_count}/{total_count}',
			f'[FAIL] Failed: {total_count - success_count}/{total_count}',
		]

		if success_count == total_count:
			summary.append('[SUCCESS] All accounts check-in successful!')
		elif success_count > 0:
			summary.append('[WARN] Some accounts check-in successful')
		else:
			summary.append('[ERROR] All accounts check-in failed')

		time_info = f'[TIME] Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

		notify_content = '\n\n'.join([time_info, '\n'.join(notification_content), '\n'.join(summary)])

		log.info('Notification content', extra={'content_length': len(notify_content)})
		notify.push_message('AnyRouter Check-in Alert', notify_content, msg_type='text')
		log.info('Notification sent due to failures or balance changes')
	else:
		log.info('All accounts successful and no balance changes detected, notification skipped')

	# 设置退出码
	sys.exit(0 if success_count > 0 else 1)


def run_main():
	"""运行主函数的包装函数"""
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		log.warning('Program interrupted by user')
		sys.exit(1)
	except Exception as e:
		log.error('Program execution error', extra={'error': str(e)})
		sys.exit(1)


if __name__ == '__main__':
	run_main()
