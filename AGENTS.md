# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.

## What this project is

`robotframework-allurevisitor` generates [Allure](https://allurereport.org/) input
files from Robot Framework results. It is an **alternative to the
`allure-robotframework` listener**: rather than hooking into a live test run, it
post-processes an existing Robot Framework `output.xml` using Robot Framework's
`ResultVisitor` API and writes Allure `*-result.json` files into a results
directory.

Use it when you have a Robot `output.xml` (e.g. from CI, a rerun, or a merged
run) and want an Allure report without re-running the tests.

## Tech stack & layout

- **Python** `>=3.13`, packaged with **hatchling**, `src/` layout.
- **Environment & dependencies are managed by [uv](https://docs.astral.sh/uv/).**
- Runtime deps: `robotframework` (the `ResultVisitor`/`ExecutionResult` API) and
  `allure-python-commons` (the Allure model + file logger).
- Dev deps (in the `dev` dependency group): `pytest`, `ruff`.

```
src/robotframework_allurevisitor/
  __init__.py     # public API: AllureResultVisitor, generate
  visitor.py      # stack-based ResultVisitor + generate(); -> AllureFileLogger
  _convert.py     # timing (to_ms), status (status_of), identity (history_id)
  _labels.py      # suite_labels(), tag_labels_and_links() via parse_tag
  cli.py          # `rf-allure` / `allurevisitor` console entry point
tests/
  conftest.py        # run_robot()/load_results() + Allure-CLI resolver helpers
  test_visitor.py    # runs real Robot suites, asserts the emitted Allure JSON
  test_e2e_report.py # full pipeline -> real Allure report (`e2e` marker)
```

## Environment setup

The environment is **uv-managed** — do not use bare `pip`, `venv`, or edit
`pyproject.toml` dependency tables by hand.

```bash
uv sync                       # create .venv and install all deps + dev group
uv add <package>              # add a runtime dependency
uv add --dev <package>        # add a dev dependency (dev group)
uv remove <package>           # remove a dependency
```

`uv add`/`uv remove` update `pyproject.toml` and `uv.lock` together — always go
through them so the lockfile stays in sync.

## Common commands

```bash
uv run pytest                 # run the test suite
uv run ruff check .           # lint
uv run ruff format .          # format
uv run rf-allure OUTPUT_XML... -o RESULTS_DIR [--clean] [--thread ID]   # generate
```

Programmatic use:

```python
from robotframework_allurevisitor import generate
generate("output.xml", "allure-results", clean=True)
```

## How the visitor maps Robot -> Allure

- **Suites -> `TestResultContainer`** (`<uuid>-container.json`); Suite
  Setup/Teardown become the container's `befores`/`afters`. Child containers and
  tests are linked via `children`.
- **Tests -> `TestResult`** (`<uuid>-result.json`).
- **Keywords and control structures (FOR/IF/WHILE/TRY/GROUP/VAR/…) -> nested
  `TestStepResult`**, kept correctly nested via a traversal stack (`_steps`).
  Keyword assignment is folded into the step name; arguments become step
  parameters.
- Status (`status_of` in `_convert.py`): `PASS->passed`, `SKIP`/`NOT RUN->skipped`,
  `FAIL->failed`, and library/import/syntax/timeout errors -> `broken`.
- Times come from the result data via `to_ms` (epoch ms), **never** wall-clock —
  conversion is reproducible. RF 7 `datetime` and legacy RF 4-6 strings both work.
- `historyId`/`testCaseId = md5(full_name)` (`history_id`) so Allure groups runs
  across reruns/CI.
- Labels (`_labels.py`): `parentSuite`/`suite`/`subSuite` from the full name,
  `framework`/`language`/`host`, optional `thread`, plus tag labels/links via
  `allure_commons.mapping.parse_tag`.
- Log messages -> HTML attachments on the owning step; embedded screenshots ->
  binary attachments resolved relative to the `output.xml` directory.

## Key behaviors to preserve

- **Suite setup/teardown detection** in `start_keyword` relies on
  `kw.type in (SETUP, TEARDOWN)` while no test is active (`self._test is None`).
  Test setup/teardown (test active) are emitted as ordinary steps.
- **Control structures use `type`/attributes for labels, not `.name`** — `For.name`
  and `If.name` are deprecated and warn in RF 8.
- **Multiple sources combine, they do NOT last-wins merge.**
  `ExecutionResult(*sources)` nests each source as a sibling sub-suite; identical
  `historyId` makes Allure group them as retries. For a single deduplicated
  result, pre-merge with `rebot --merge`.
- **Partial output**: `generate()` wraps parse+visit so a truncated `output.xml`
  warns instead of crashing. `ExecutionResult` parses eagerly, so an unparseable
  file recovers nothing — by design.

## Conventions for changes

- Keep mapping logic in `visitor.py`; keep conversion helpers in `_convert.py` /
  `_labels.py`; keep `cli.py` thin.
- Robot model objects are duck-typed across RF versions — prefer `getattr(...)`
  with sensible fallbacks over hard attribute access.
- Add/adjust a test in `tests/` for any behavior change. Tests run real Robot
  suites via `python -m robot` (see `conftest.py`), so they are self-contained —
  no committed `output.xml` fixtures.
- Run `uv run ruff check .` and `uv run pytest` before declaring work done.
- Target line length is 100 (`tool.ruff` in `pyproject.toml`).

## End-to-end test (`e2e` marker)

`test_e2e_report.py` runs Robot → the packaged `rf-allure` CLI (subprocess, so
the entry point is exercised) → a real Allure report, then asserts the report's
`widgets/summary.json` statistics and `data/test-cases/` count.

- Select/deselect with `uv run pytest -m e2e` / `-m "not e2e"`.
- `resolve_allure_cli()` in `conftest.py` prefers `allure` on `PATH`, else
  `npx allure-commandline` (needs Node + Java); `generate_allure_report()`
  **skips** (never fails) when no generator is resolvable or it can't run — so
  the converter is never blamed for a missing/broken external CLI.
- Assert on report *data* (`summary.json`, `data/test-cases/`), not HTML, since
  data is the stable cross-version contract.
