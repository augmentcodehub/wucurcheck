# Python Rules

This file is mandatory for all work under `python/src`.

## Hard Rules

- Keep business logic in `core/`.
- Keep external adapters in `adapters/`.
- Keep command entrypoints in `cli/`.
- Keep maintenance/generation jobs in `tools/`.
- Keep pure utility functions (no IO, no side effects) in `lib/`.
- Keep provider implementations (login/checkin/balance per site) in `providers/`.
- Keep pipeline orchestrations (multi-step workflows) in `pipelines/`.
- Do not recreate `scripts/`; keep compatibility shims only at the root wrappers if absolutely necessary.
- Do not add new business logic to `utils/`.
- Put generated files, exports, caches, and databases in `python/artifacts/`.
- Do not create new top-level Python source folders outside `python/src/`.

## Folder Intent

- `core/`: domain models, application use cases, ports (interfaces).
- `adapters/`: HTTP, persistence, notifications, registration adapters.
- `cli/`: user-facing Python entrypoints. Unified entry: `register.py` for all providers.
- `tools/`: batch jobs, export/import, generators.
- `lib/`: pure functions and shared modules (no IO in pure functions, IO helpers clearly marked).
- `providers/`: per-site provider implementations registered via `lib/registry.py`.
- `pipelines/`: multi-step orchestrations that compose providers (e.g. login → checkin → balance).
- `utils/`: small shared helpers only (config, logger, notify).

## Refactoring Rule

- Before moving or deleting files, check git history for dependents.
- Prefer one responsibility per module.
- Remove compatibility shims after all call sites are migrated.
- Mark deprecated files with `# DEPRECATED: Use xxx instead` at the top.

## Registration Entry Points

- `cli/register.py` — unified entry for all providers (`--provider kiro|wucur`).
- `cli/register_kiro.py` — DEPRECATED, use `cli/register.py --provider kiro`.
- `cli/register_wucur.py` — DEPRECATED, use `cli/register.py --provider wucur`.

## Checkin Entry Points

- `cli/checkin.py` — full checkin with WAF bypass (used by `checkin.yml`).
- `scripts/checkin_batch.py` — lightweight batch via Pipeline+Provider (used by `checkin_batch.yml`).
