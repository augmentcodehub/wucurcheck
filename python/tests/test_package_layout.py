from importlib import import_module


def test_core_cli_packages_are_importable() -> None:
	for module_name in (
		'core',
		'core.application',
		'core.infrastructure',
		'core.ports',
		'cli',
		'adapters',
		'adapters.http',
		'adapters.checkin',
		'adapters.persistence',
		'tools',
		'tools.account_generation',
		'tools.export',
		'tools.pipeline',
		'tools.register',
		'core.infrastructure',
		'core.infrastructure.sqlite_account_repository',
		'core.infrastructure.cloudflare_kv_account_repository',
		'adapters.messages',
		'scripts',
		'wucur_cli',
	):
		module = import_module(module_name)
		assert module is not None
