from pathlib import Path


def test_worker_layout_has_cloudflare_entrypoint() -> None:
	worker_dir = Path('worker-dashboard')
	assert worker_dir.is_dir()
	assert (worker_dir / 'wrangler.toml').is_file()
	assert (worker_dir / 'src' / 'index.ts').is_file()
