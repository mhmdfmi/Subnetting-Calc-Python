# Changelog

## [0.1.3] - 2026-04-09

- Updated version to 0.1.3 (metadata release)

## [0.1.2] - 2026-04-08

- Added global build/install helper scripts: `build_global.ps1` and `build_global.sh`.
- Updated packaging documentation and release metadata for version 0.1.2.
- Ensured `.coverage` is ignored by git and cannot be pushed to the repository.
- Fixed package metadata version mismatch in `subnet_calc.py`.

## [0.1.1] - 2026-04-08

- Added extensive unit tests for subnet calculation utilities, VLSM logic, error handling, and edge cases.
- Added CLI integration tests covering count, reverse, vlsm, supernet, overlap, and eui64 commands.
- Added linting and quality tooling support with Black, Flake8, and MyPy.
- Added CI workflow updates for GitHub Actions to run tests, coverage, formatting, linting, and type checks.
- Added improved config and dependency metadata for optional test and output dependencies.

## [0.1.0] - 2026-04-08

- Initial release with CLI and library support for IPv4/IPv6 subnet calculations.
- Added generator-based subnet creation to reduce memory usage for large networks.
- Added caching for repeated helper requests.
- Added detailed docstrings to main functions and utility helpers.
- Added packaging metadata with `pyproject.toml`.
- Added `README.md` with installation, usage, and sample output.
