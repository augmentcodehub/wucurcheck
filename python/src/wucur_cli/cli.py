#!/usr/bin/env python3
"""
Canonical CLI for the Wucur helper workflows.

The CLI keeps a small, readable command surface and forwards execution to the
existing scripts so the repository stays compatible with current workflows.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CommandSpec:
	name: str
	summary: str
	module: str
	example: str
	detail: str = ''


COMMANDS: list[CommandSpec] = [
	CommandSpec(
		name='generate',
		summary='按规则批量生成账号 JSON，不执行注册',
		module='tools.account_generation.generate_accounts',
		example='uv run wucur generate --stdout',
		detail='先生成账号清单，适合做批量检查或下游分发。',
	),
	CommandSpec(
		name='make-test',
		summary='生成 1 个可直接注册的测试账号 JSON',
		module='tools.account_generation.make_wucur_test_account',
		example='uv run wucur make-test --sequence 1',
		detail='用于快速产出单个测试账号文件。',
	),
	CommandSpec(
		name='register',
		summary='读取单个账号 JSON 并执行注册',
		module='tools.register.register_one_account',
		example='uv run wucur register --file one-account.json --skip-checkin',
		detail='输入必须是单个 JSON 对象。',
	),
	CommandSpec(
		name='register-db',
		summary='注册单个账号并写入 SQLite',
		module='tools.register.register_one_account_to_db',
		example='uv run wucur register-db --file one-account-checkin-next.json',
		detail='适合把成功注册的账号沉到本地数据库。',
	),
	CommandSpec(
		name='query',
		summary='查询 SQLite 里的注册记录',
		module='cli.query_wucur_accounts_db',
		example='uv run wucur query --limit 50',
		detail='查看最近账号、密码、注册时间和余额信息。',
	),
	CommandSpec(
		name='export',
		summary='导出 SQLite 为 JSON 和 CSV',
		module='tools.export.export_wucur_accounts',
		example='uv run wucur export --stdout-json',
		detail='JSON 输出就是 `ANYROUTER_ACCOUNTS` 可直接使用的数组格式。',
	),
	CommandSpec(
		name='pipeline',
		summary='一条命令跑完生成、注册、写库和导出',
		module='tools.pipeline.run_wucur_pipeline',
		example='uv run wucur pipeline --sequence 15',
		detail='本地整条流程的默认入口。',
	),
	CommandSpec(
		name='register-wrapper',
		summary='先按规则生成 1 个账号，再调用注册脚本',
		module='tools.account_generation.register_wucur_wrapper',
		example='uv run wucur register-wrapper --config register_wucur_wrapper.json',
		detail='适合规则驱动的单账号注册流程。',
	),
	CommandSpec(
		name='register-wucur',
		summary='直接调用底层 Wucur 注册、登录、签到脚本',
		module='cli.register_wucur',
		example='uv run wucur register-wucur --username user@example.com --password pass',
		detail='适合已经有账号密码时直接执行底层流程。',
	),
]


COMMAND_MAP = {spec.name: spec for spec in COMMANDS}


def ensure_src_dir_on_path() -> None:
	src_dir = str(SRC_DIR)
	if src_dir not in sys.path:
		sys.path.insert(0, src_dir)


def format_general_help() -> str:
	lines = [
		'Wucur 命令总览',
		'',
		'用法:',
		'  uv run wucur <command> [args...]',
		'',
		'命令:',
	]
	for spec in COMMANDS:
		lines.append(f'  {spec.name:<12} {spec.summary}')
	lines.extend(
		[
			'',
			'帮助:',
			'  uv run wucur help',
			'  uv run wucur help export',
			'  uv run wucur <command> --help',
		]
	)
	return '\n'.join(lines)


def format_command_help(spec: CommandSpec) -> str:
	lines = [
		f'命令: {spec.name}',
		f'作用: {spec.summary}',
		f'入口模块: {spec.module}',
		f'示例: {spec.example}',
	]
	if spec.detail:
		lines.append(f'说明: {spec.detail}')
	return '\n'.join(lines)


def print_general_help() -> None:
	print(format_general_help())


def print_command_help(command_name: str) -> int:
	spec = COMMAND_MAP.get(command_name)
	if spec is None:
		print(f'[FAILED] Unknown command: {command_name}')
		print()
		print_general_help()
		return 1
	print(format_command_help(spec))
	return 0


def run_command(command_name: str, args: list[str]) -> int:
	spec = COMMAND_MAP.get(command_name)
	if spec is None:
		print(f'[FAILED] Unknown command: {command_name}')
		print()
		print_general_help()
		return 1

	try:
		ensure_src_dir_on_path()
		module = import_module(spec.module)
	except Exception as exc:
		print(f'[FAILED] Failed to load command module {spec.module}: {exc}')
		return 1

	main = getattr(module, 'main', None)
	if main is None:
		print(f'[FAILED] Command module {spec.module} does not expose main()')
		return 1

	try:
		result = main(args)
	except TypeError:
		result = invoke_main(main, spec.module, args)
	return int(result or 0)


def invoke_main(main: object, module_name: str, args: list[str]) -> int:
	old_argv = sys.argv
	sys.argv = [f'{module_name}.py', *args]
	try:
		try:
			result = main()
		except SystemExit as exc:
			code = exc.code
			if code is None:
				return 0
			if isinstance(code, int):
				return code
			print(code)
			return 1
	finally:
		sys.argv = old_argv
	return int(result or 0)


def main(argv: list[str] | None = None) -> int:
	args = list(sys.argv[1:] if argv is None else argv)
	if not args:
		print_general_help()
		return 0

	first = args[0]
	if first in {'-h', '--help'}:
		print_general_help()
		return 0
	if first == 'help':
		if len(args) == 1:
			print_general_help()
			return 0
		return print_command_help(args[1])

	return run_command(first, args[1:])


if __name__ == '__main__':
	sys.exit(main())
