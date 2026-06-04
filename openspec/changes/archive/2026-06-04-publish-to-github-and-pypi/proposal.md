## Why

The converter is implemented, tested (unit + end-to-end), and documented locally, but it lives only on this machine: there is no license, the package metadata is still the `uv init` placeholder set, and it is neither hosted nor installable. To let others use it, the project needs to become a proper, licensed, metadata-complete distribution — published to PyPI and hosted in a public GitHub repository.

## What Changes

- Add an **Apache-2.0** `LICENSE` and declare it in package metadata (SPDX expression + `license-files`).
- Complete the **PyPI package metadata** in `pyproject.toml`: authors, keywords, Trove classifiers (Python 3.13, Robot Framework, testing/reporting), and `project.urls` (Homepage, Repository, Issues). Keep `name = robotframework-allurevisitor`, `version = 0.1.0`.
- Add release/hosting **documentation**: polish `README.md` for PyPI rendering (install-from-PyPI instructions, badges), add a `CHANGELOG.md` with the `0.1.0` entry.
- Ensure the repo is **publish-clean**: extend `.gitignore` so local/generated artifacts (`dist/`, `reports/`, `allure-results/`, `.venv`, and local agent dirs `.claude/`/`.opencode/`) are not committed; commit the source, tests, specs, lockfile, and docs.
- Create the public **GitHub repository** `manykarim/robotframework-allurevisitor` with a `main` branch and push all needed files.
- **Build** distributables with `uv build` (sdist + wheel) and verify the wheel installs and exposes the `rf-allure` console script.
- **Publish to PyPI** with `uv publish` using an API token supplied at run time via `UV_PUBLISH_TOKEN` (never stored in the repo).

## Capabilities

### New Capabilities
- `package-distribution`: The project is a properly-licensed, metadata-complete Python distribution — building cleanly into an installable sdist/wheel that exposes the CLI, hosted in a public GitHub repository on a `main` branch, and published to PyPI.

### Modified Capabilities
<!-- None: existing conversion/CLI/e2e capabilities are unchanged. -->

## Impact

- **Files added:** `LICENSE` (Apache-2.0), `CHANGELOG.md`.
- **Files modified:** `pyproject.toml` (license + metadata), `README.md` (PyPI-facing docs/badges), `.gitignore` (ignore generated/local dirs).
- **Runtime dependencies:** none changed.
- **External, outward-facing actions (require explicit go-ahead at apply time):**
  - Create a **public** GitHub repo under `manykarim/` (uses the already-authenticated `gh` CLI) and push commits.
  - **Publish to PyPI** — effectively irreversible: the project name is claimed and version `0.1.0` cannot be re-uploaded once accepted. Requires a PyPI API token provided by the user.
- **Out of scope (follow-ups):** GitHub Actions CI/release automation (trusted publishing), TestPyPI dry-run, and a docs site — this change does a first manual, token-based release.
