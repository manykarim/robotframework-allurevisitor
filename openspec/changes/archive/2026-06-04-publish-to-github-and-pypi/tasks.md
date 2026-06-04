## 1. License and metadata

- [x] 1.1 Add a top-level `LICENSE` file with the full Apache-2.0 text
- [x] 1.2 Declare the license in `pyproject.toml` via `license = "Apache-2.0"` and `license-files = ["LICENSE"]` (no `License ::` Trove classifier)
- [x] 1.3 Complete `pyproject.toml` metadata: `authors`, `keywords`, Trove `classifiers` (Python 3 / 3.13, Framework :: Robot Framework, Development Status, Intended Audience, Topic :: Software Development :: Testing, OS Independent), and `project.urls` (Homepage, Repository, Issues)

## 2. Documentation

- [x] 2.1 Add install-from-PyPI instructions and PyPI/license badges to `README.md`, ensuring it renders as the package long description
- [x] 2.2 Add `CHANGELOG.md` with a `0.1.0` entry describing the initial release

## 3. Publish-clean repository

- [x] 3.1 Extend `.gitignore` to ignore `dist/`, `reports/`, `allure-results/`, demo `output.xml`/`log.html`/`report.html`, and local agent dirs `.claude/`/`.opencode/`
- [x] 3.2 Ensure the working branch is `main` (rename `master` -> `main`)
- [x] 3.3 Review `git status` and stage the clean file set (`src/`, `tests/`, `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE`, `CHANGELOG.md`, `AGENTS.md`, `.gitignore`, `.python-version`, `openspec/`); create the initial commit

## 4. Build and verify

- [x] 4.1 Run `uv build` and confirm both an sdist (`.tar.gz`) and a wheel (`.whl`) are produced under `dist/`
- [x] 4.2 Install the built wheel into a clean/isolated environment and verify `rf-allure --help` runs and `import robotframework_allurevisitor` succeeds
- [x] 4.3 Run `uv run ruff check .` and `uv run pytest` (the e2e test may skip) and confirm everything passes

## 5. GitHub repository (confirm before executing)

- [x] 5.1 Create the public repo `manykarim/robotframework-allurevisitor` and wire `origin` (e.g. `gh repo create ... --public --source . --remote origin --push`); if it already exists, add the remote and push instead
- [x] 5.2 Confirm the remote default branch is `main` and the pushed tree contains source, tests, docs, license, and specs
- [x] 5.3 Tag `v0.1.0` and create a lightweight GitHub release

## 6. Publish to PyPI (confirm before executing; final, irreversible step)

- [ ] 6.1 Publish with `uv publish` using the user-provided token via `UV_PUBLISH_TOKEN` (never written to the repo)
- [ ] 6.2 Verify the release: `pip install robotframework-allurevisitor` in a clean environment installs and exposes `rf-allure`
