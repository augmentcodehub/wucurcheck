#!/usr/bin/env python3
"""
Generate rule-based accounts without registering them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
	from .account_rule_engine import generate_accounts, load_rule_config, write_example_rule_config
except ImportError:  # pragma: no cover - direct script execution fallback
	from account_rule_engine import generate_accounts, load_rule_config, write_example_rule_config

DEFAULT_CONFIG_PATH = Path('register_wucur_wrapper.json')
DEFAULT_OUTPUT_PATH = Path('generated_accounts.json')


try:
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')
	sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # nosec B110
	pass


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description='Generate rule-based account sets without calling the registration script.')
	parser.add_argument('--config', default=str(DEFAULT_CONFIG_PATH), help='Path to account generation config')
	parser.add_argument('--output', default=str(DEFAULT_OUTPUT_PATH), help='Path to the generated account JSON file')
	parser.add_argument('--init-config', action='store_true', help='Create an example config file and exit')
	parser.add_argument('--stdout', action='store_true', help='Print generated accounts to stdout')
	args = parser.parse_args(argv)

	config_path = Path(args.config)
	output_path = Path(args.output)

	if args.init_config:
		write_example_rule_config(config_path)
		print(f'[SUCCESS] Example config written to {config_path}')
		return 0

	try:
		config = load_rule_config(config_path)
		accounts = generate_accounts(config)
	except Exception as exc:
		print(f'[FAILED] {exc}')
		return 1

	output_path.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding='utf-8')
	print(f'[SUCCESS] Generated {len(accounts)} account(s) to {output_path}')

	if args.stdout:
		print(json.dumps(accounts, ensure_ascii=False, indent=2))

	return 0


if __name__ == '__main__':
	sys.exit(main())
