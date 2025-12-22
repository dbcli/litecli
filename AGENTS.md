# Repository Guidelines

## Project Structure & Module Organization
- `litecli/`: Core package. Entry point `main.py`, SQL execution in `sqlexecute.py`, completion in `packages/completion_engine.py`, special commands under `packages/special/`.
- `tests/`: Pytest suite (files like `test_*.py`). Test data under `tests/data/`.
- `screenshots/`: Images used in README.
- Config template: `litecli/liteclirc` (user config is created under `~/.config/litecli/config` or `%LOCALAPPDATA%/dbcli/litecli/config`).

## Build, Test, and Development Commands
- Create env: `python -m venv .venv && source .venv/bin/activate`.
- Install dev deps: `pip install -e .[dev]`.
- Run all tests + coverage: `tox`.
- Extra tests with SQLean: `tox -e sqlean` (installs `[sqlean]` extras).
- Run tests directly: `pytest -q` or focused: `pytest -k keyword`.
- Launch CLI locally: `litecli path/to.db`.

### Ruff (lint/format)
- Full style pass: `tox -e style` (runs `ruff check --fix` and `ruff format`).
- Direct commands:
  - Lint: `ruff check` (add `--fix` to auto-fix)
  - Format: `ruff format`

## ty (type checking)
- Repo-wide `ty check -v`
- Per-package: `ty check litecli -v`
- Notes:
  - Config is in `pyproject.toml` (target Python 3.9, stricter settings).

## Coding Style & Naming Conventions
- Formatter/linter: Ruff (configured via `.pre-commit-config.yaml` and `tox`).
- Indentation: 4 spaces. Line length: 140 (see `pyproject.toml`).
- Naming: modules/functions/variables `snake_case`; classes `CamelCase`; tests `test_*.py`.
- Keep imports sorted and unused code removed (ruff enforces).
- Use lowercase type hints for dict, list, tuples etc.
- Use | for Unions and | None for Optional.

## Testing Guidelines
- Framework: Pytest with coverage (`coverage run -m pytest` via tox).
- Location: place new tests in `tests/` alongside related module area.
- Conventions: name files `test_<unit>.py`; use fixtures from `tests/conftest.py`.
- Quick check: `pytest -q`; coverage report via `tox` or `coverage report -m`.

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise scope (e.g., `fix: handle NULL types`). Reference issues (`#123`) when relevant.
- Update `CHANGELOG.md` for user-visible changes.
- PRs: include clear description, steps to reproduce/verify, and screenshots or snippets for CLI output when helpful. Use the PR template.
- Ensure CI passes (tests + ruff). Re-run `tox -e style` before requesting review.

## Changelog Discipline
- Always add an "Unreleased" section at the top of `CHANGELOG.md` when making changes.
- Keep entries succinct; avoid overly detailed technical notes.
- Group under "Features", "Bug Fixes", and "Internal" when applicable.

## Security & Configuration Tips
- Do not commit local databases or secrets. Use files under `tests/data/` for fixtures.
- User settings live outside the repo; document defaults by editing `litecli/liteclirc`.
