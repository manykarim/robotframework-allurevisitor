## Context

The library is complete and tested but unpublished. This change turns it into a public, installable distribution: license, metadata, docs, a public GitHub repo on `main`, and a first PyPI release. Verified prerequisites: `gh` is authenticated as `manykarim`, there is **no git remote and no commits yet**, the current branch is `master`, `uv build`/`uv publish` are available, and there is **no LICENSE**. User decisions: **Apache-2.0** license; **local `uv build` + `uv publish` with an API token** (no CI/trusted publishing this round).

## Goals / Non-Goals

**Goals:**
- Apache-2.0 license in the repo and in distribution metadata (PEP 639 SPDX).
- Release-ready `pyproject.toml` metadata (authors, classifiers, keywords, URLs).
- A clean committed file set (no generated/local artifacts) on a `main` branch.
- A public GitHub repo `manykarim/robotframework-allurevisitor` with everything pushed.
- A built, verified sdist+wheel published to PyPI and installable via `pip`.
- PyPI-facing docs (README install section + badges, CHANGELOG `0.1.0`).

**Non-Goals:**
- GitHub Actions CI or trusted-publishing automation (follow-up).
- TestPyPI dry-run (user chose to publish straight to PyPI).
- A hosted docs site, CONTRIBUTING guide, or issue templates.
- Version bumping / release tooling beyond the single `0.1.0` release.

## Decisions

### Apache-2.0 via PEP 639 SPDX metadata
Add a full `LICENSE` file (Apache-2.0). In `pyproject.toml` use `license = "Apache-2.0"` and `license-files = ["LICENSE"]`, and **do not** also add a `License ::` Trove classifier (PEP 639 / Metadata 2.4 disallows mixing an SPDX expression with license classifiers; hatchling errors on it).
- *Why:* modern, unambiguous, carried into the wheel METADATA; matches the hatchling backend already in use.
- *Verify at apply:* hatchling version supports PEP 639 (`uv build` succeeds); if the installed hatchling is too old, fall back to `license = {text = "Apache-2.0"}` + the classifier.

### Metadata content
`authors = [{name = "Many Kasiriha", email = "many.kasiriha@gmail.com"}]`; `keywords = ["robotframework","allure","testing","reporting","allure-report","output.xml"]`; classifiers for `Development Status :: 4 - Beta`, `Intended Audience :: Developers`, `Programming Language :: Python :: 3 / :: 3.13`, `Framework :: Robot Framework`, `Topic :: Software Development :: Testing`, `Operating System :: OS Independent`; `project.urls` Homepage/Repository → the GitHub URL, Issues → `/issues`.
- *Why:* discoverability and correct PyPI presentation.

### `main` branch from the current empty history
There are no commits. Plan: create the first commit on `main` (rename `master`→`main` with `git branch -m main`, or `git checkout -b main`), so the default branch is `main` from the start.
- *Why:* satisfies the "main branch" requirement cleanly without a later default-branch change.

### Repo creation with the gh CLI
Use `gh repo create manykarim/robotframework-allurevisitor --public --source . --remote origin --push` after the local `main` commit exists.
- *Why:* one command creates the public repo, wires `origin`, and pushes. `gh` is already authenticated.
- *Idempotency:* if the repo already exists, skip creation and just add the remote + push.

### Publish-clean .gitignore
Extend `.gitignore` to ignore `dist/`, `reports/`, `allure-results/`, `**/output.xml`/`log.html`/`report.html` demo outputs, and the local agent dirs `.claude/`, `.opencode/`. Keep `openspec/` (specs are part of the project), `uv.lock`, `.python-version`, `tests/`, `src/`.
- *Why:* the public repo should contain source + specs + docs, not build output or local tooling. The `reports/demo/` artifacts generated earlier must not be committed.

### Build + verify before publish
`uv build` → `dist/*.whl` + `dist/*.tar.gz`. Verify by `pip install`-ing the wheel into a throwaway environment (e.g. `uv run --isolated --with dist/*.whl ...` or a fresh venv) and checking `rf-allure --help` and `import robotframework_allurevisitor`.
- *Why:* catch packaging errors (missing modules, broken entry point) before the irreversible upload.

### Token-based publish, token never stored
`uv publish` reads `UV_PUBLISH_TOKEN` from the environment, provided by the user at run time. Do not write the token to any file. Run order: build → verify → push to GitHub → publish to PyPI last (so the repo is live before the irreversible upload).
- *Why:* the user's chosen mechanism; keeps credentials out of the repo and history.

## Risks / Trade-offs

- **PyPI publish is irreversible** (name claimed; `0.1.0` cannot be re-uploaded) → Verify the built wheel locally first; publish as the final step; if anything looks wrong, optionally do a one-off TestPyPI upload before the real one (the user opted to skip, but it remains a safety valve).
- **PyPI name `robotframework-allurevisitor` could be taken** → `uv publish` will fail clearly; if so, pause and ask the user for an alternative name (would also require updating metadata/repo).
- **PEP 639 metadata vs older hatchling** → `uv build` is the gate; documented fallback to `license = {text = ...}` + classifier.
- **Outward-facing actions need explicit go-ahead** → Repo creation and PyPI upload are confirmed at apply time, not run silently; the apply order surfaces each before executing.
- **Accidentally committing local/generated files** → `.gitignore` updated and `git status` reviewed before the first commit; the earlier `reports/demo/` report (~2 MB) must be excluded.
- **No CI means quality relies on local checks** → Run `ruff` + `pytest` (incl. e2e where possible) before committing; CI is an explicit follow-up.

## Migration Plan

1. Add `LICENSE`, update `pyproject.toml` metadata, add `CHANGELOG.md`, polish `README.md`, extend `.gitignore`.
2. `uv build`; verify the wheel installs and the CLI works.
3. `git` init flow: ensure `main`, review `git status`, commit the clean file set.
4. Create the public GitHub repo and push `main` (confirm first).
5. `uv publish` with the user-provided token (confirm first; final step).
6. Post-checks: repo is public on `main`; `pip install robotframework-allurevisitor` works.

Rollback: pre-publish steps are local and revertible (delete branch/commit, `gh repo delete`). After a PyPI upload, `0.1.0` cannot be replaced — a fix requires a new version (`0.1.1`); yanking is possible but not deletion.

## Open Questions

- Final PyPI long-description badges (build/PyPI/license) — include now or after CI exists? (Lean: add PyPI + license badges now; add a CI badge when CI lands.)
- Should `0.1.0` be tagged (`git tag v0.1.0`) and a GitHub Release created? (Lean: yes — tag and a lightweight GitHub release for traceability.)
