"""Legacy compatibility package for old ``scripts.*`` imports."""

from __future__ import annotations

import importlib
import sys


_ALIASES = {
	'account_registry_db': 'adapters.persistence.sqlite.account_registry_db',
	'account_rule_engine': 'tools.account_generation.account_rule_engine',
	'checkin_due_cli': 'cli.checkin_due_cli',
	'checkin_due_domain': 'core.domain',
	'checkin_due_repository': 'adapters.persistence.sqlite.checkin_due_repository',
	'checkin_due_service': 'adapters.checkin.checkin_due_service',
	'export_wucur_accounts': 'tools.export.export_wucur_accounts',
	'generate_accounts': 'tools.account_generation.generate_accounts',
	'make_wucur_test_account': 'tools.account_generation.make_wucur_test_account',
	'query_wucur_accounts_db': 'cli.query_wucur_accounts_db',
	'register_one_account_to_db': 'tools.register.register_one_account_to_db',
	'register_wucur': 'cli.register_wucur',
	'register_wucur_wrapper': 'tools.account_generation.register_wucur_wrapper',
	'run_wucur_pipeline': 'tools.pipeline.run_wucur_pipeline',
	'wucur': 'wucur_cli.cli',
	'wucur_client': 'adapters.http.wucur_client',
}


for legacy_name, target_name in _ALIASES.items():
	module = importlib.import_module(target_name)
	sys.modules[f'{__name__}.{legacy_name}'] = module
	globals()[legacy_name] = module


__all__ = sorted(_ALIASES)
