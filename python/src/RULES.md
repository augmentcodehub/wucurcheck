# Python Rules

This file is mandatory for all work under `python/src`.

## Hard Rules

- Keep business logic in `core/`.
- Keep external adapters in `adapters/`.
- Keep command entrypoints in `cli/`.
- Keep maintenance/generation jobs in `tools/`.
- Do not recreate `scripts/`; keep compatibility shims only at the root wrappers if absolutely necessary.
- Do not add new business logic to `utils/`.
- Put generated files, exports, caches, and databases in `python/artifacts/`.
- Do not create new top-level Python source folders outside `python/src/`.

## Folder Intent

- `core/`: domain models, application use cases, ports.
- `adapters/`: HTTP, persistence, notifications, logging adapters.
- `cli/`: user-facing Python entrypoints.
- `tools/`: batch jobs, export/import, generators, pipelines.
- `utils/`: small shared helpers only.

## Refactoring Rule

- Before moving or deleting files, create a backup under `python/_backup/`.
- Prefer one responsibility per module.
- Remove compatibility shims after all call sites are migrated.
