#!/usr/bin/env python3
"""
Shared Wucur HTTP helpers.
"""

from __future__ import annotations

import json
import time

import httpx

from utils.config import AccountConfig
from utils.logger import get_logger

log = get_logger('adapters.http.wucur_client')


BASE_URL = 'http://wucur.com:6543'
REGISTER_PATH = '/api/user/register'
LOGIN_PATH = '/api/user/login'
USER_INFO_PATH = '/api/user/self'
CHECKIN_PATH = '/api/user/checkin'
TRANSIENT_STATUS_CODES = {500, 502, 503, 504}


def build_headers(referer_path: str, base_url: str = BASE_URL) -> dict[str, str]:
	return {
		'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
		'Accept': 'application/json, text/plain, */*',
		'Content-Type': 'application/json',
		'Origin': base_url,
		'Referer': f'{base_url}{referer_path}',
	}


def parse_response(response: httpx.Response) -> dict:
	try:
		return response.json()
	except json.JSONDecodeError:
		raw_text = response.text[:200] if response.text else '<empty body>'
		return {
			'success': False,
			'message': f'Invalid JSON response: HTTP {response.status_code}, body={raw_text}',
		}


def build_login_payload(account: AccountConfig) -> dict:
	return {
		'username': account.username,
		'password': account.password,
	}


def extract_token_from_login_response(response: httpx.Response) -> str | None:
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
	try:
		data = response.json()
	except json.JSONDecodeError:
		return None

	return extract_login_user_id_from_payload(data)


def extract_login_user_id_from_payload(data: object) -> str | None:
	if not isinstance(data, dict):
		return None

	data_node = data.get('data')
	if isinstance(data_node, dict):
		user_id = data_node.get('id')
		if user_id is not None:
			text = str(user_id).strip()
			if text:
				return text

	user_data = data.get('user')
	if isinstance(user_data, dict):
		user_id = user_data.get('id')
		if user_id is not None:
			text = str(user_id).strip()
			if text:
				return text

	user_id = data.get('id')
	if user_id is not None:
		text = str(user_id).strip()
		if text:
			return text

	return None


def login_with_bearer_token(client: httpx.Client, account_name: str, provider_config, account: AccountConfig) -> str | None:
	if not account.username or not account.password:
		log.error('Missing username/password for bearer login', extra={'account': account_name})
		return None

	if not provider_config.login_api_path:
		log.error('Provider missing login_api_path', extra={'account': account_name, 'provider': provider_config.name})
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
	if not account.username or not account.password:
		log.error('Missing username/password for password session login', extra={'account': account_name})
		return None

	if not provider_config.login_api_path:
		log.error('Provider missing login_api_path', extra={'account': account_name, 'provider': provider_config.name})
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


def get_user_info(client: httpx.Client, headers: dict, user_info_url: str) -> dict:
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


def extract_balance_summary(user_info: dict | None) -> dict[str, float] | None:
	if not isinstance(user_info, dict) or not user_info.get('success'):
		return None
	if 'quota' in user_info and 'used_quota' in user_info:
		return {
			'quota': round(float(user_info.get('quota', 0)), 2),
			'used_quota': round(float(user_info.get('used_quota', 0)), 2),
		}
	data = user_info.get('data', {})
	return {
		'quota': round(data.get('quota', 0) / 500000, 2),
		'used_quota': round(data.get('used_quota', 0) / 500000, 2),
	}


def checkin_account(client: httpx.Client, headers: dict, sign_in_url: str) -> dict:
	checkin_headers = headers.copy()
	checkin_headers.update({'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'})
	response = client.post(sign_in_url, headers=checkin_headers, timeout=30)
	data = parse_response(response)
	if response.status_code != 200:
		log.warning('Checkin HTTP error', extra={'status': response.status_code, 'url': sign_in_url})
		return {'success': False, 'message': f'HTTP {response.status_code}', 'raw': data}
	log.info('Checkin response', extra={'success': data.get('success'), 'message': str(data.get('message', ''))[:80]})
	return data


def register_account(client: httpx.Client, username: str, password: str) -> dict:
	last_result = None
	for attempt in range(1, 4):
		response = client.post(
			f'{BASE_URL}{REGISTER_PATH}',
			headers=build_headers('/register'),
			json={'username': username, 'password': password},
			timeout=30,
		)
		data = parse_response(response)
		last_result = data

		if response.status_code == 200 and data.get('success'):
			log.info('Register success', extra={'username': username})
			return data

		raw_message = str(data.get('message', ''))
		should_retry = response.status_code in TRANSIENT_STATUS_CODES or 'Invalid JSON response' in raw_message
		if not should_retry or attempt == 3:
			log.warning('Register failed', extra={'username': username, 'status': response.status_code, 'message': raw_message[:80]})
			if response.status_code != 200:
				return {'success': False, 'message': f'HTTP {response.status_code}', 'raw': data}
			return data

		log.warning('Register transient failure, retrying', extra={'username': username, 'attempt': attempt, 'status': response.status_code, 'message': raw_message[:80]})
		time.sleep(attempt)

	log.error('Register exhausted retries', extra={'username': username})
	return last_result if isinstance(last_result, dict) else {'success': False, 'message': 'Unknown register failure'}


def login_account(client: httpx.Client, username: str, password: str) -> dict:
	log.info('Login attempt', extra={'username': username, 'has_password': bool(password)})
	response = client.post(
		f'{BASE_URL}{LOGIN_PATH}',
		headers=build_headers('/login'),
		json={'username': username, 'password': password},
		timeout=30,
	)
	data = parse_response(response)
	if response.status_code != 200:
		log.warning('Login HTTP error', extra={'username': username, 'status': response.status_code})
		return {'success': False, 'message': f'HTTP {response.status_code}', 'raw': data}
	if not data.get('success'):
		log.warning('Login rejected', extra={'username': username, 'message': str(data.get('message', ''))[:80]})
		return data
	if 'session' not in client.cookies:
		log.warning('Login no session cookie', extra={'username': username})
		return {'success': False, 'message': 'Login succeeded but session cookie was not found', 'raw': data}
	log.info('Login success', extra={'username': username})
	return data

