## Why

The current test suite verifies the conversion in isolation: it runs Robot Framework, converts `output.xml`, and asserts the emitted Allure JSON. It never proves that those JSON files actually produce a valid Allure **report** — the real consumer. A broken or subtly-incompatible file (a field Allure rejects, a bad `historyId`, a mis-typed attachment) would pass today and only surface when a user runs `allure generate`. We need a true end-to-end test that exercises the whole pipeline — Robot run → `rf-allure` conversion → Allure report — and asserts the report reflects the run.

## What Changes

- Add an end-to-end test that drives the full pipeline: execute a representative Robot Framework suite, convert it via the installed `rf-allure` console script (subprocess, so packaging is exercised too), generate a real Allure HTML report, and assert the report is well-formed and statistically correct.
- Add a representative fixture suite exercising every status (passed/failed/skipped/broken), tags (severity/feature), suite setup/teardown, control structures, and a log attachment, so the report's summary and behaviors reflect a realistic run.
- Add an **Allure CLI resolver** that uses `allure` when on `PATH`, otherwise falls back to `npx allure-commandline` (Java-backed) when Node and Java are available, and **skips the test gracefully** when no generator is available — so the suite stays green on machines without Allure while actually generating a report where possible.
- Register a `e2e` pytest marker so the end-to-end test can be selected/deselected (`pytest -m e2e` / `pytest -m "not e2e"`); the test still runs by default and self-skips when unsatisfiable.
- Assert on the generated report: `index.html` exists, `widgets/summary.json` statistics match the run's status counts, and `data/test-cases/` contains one entry per test.
- Document the end-to-end flow and how to install/obtain the Allure CLI.

## Capabilities

### New Capabilities
- `e2e-report-verification`: An automated end-to-end test guarantee that the Robot Framework → `rf-allure` → Allure report pipeline produces a valid, statistically-correct Allure HTML report, with a portable Allure-CLI resolver and graceful skip when no generator is available.

### Modified Capabilities
<!-- None: this adds a verification capability; existing conversion specs are unchanged. -->

## Impact

- **Tests:** new `tests/test_e2e_report.py`; new fixture suite text; a shared Allure-CLI resolver/skip helper (in `tests/conftest.py`).
- **Config:** `pyproject.toml` registers the `e2e` pytest marker.
- **Runtime dependencies:** none added. The report generator is the external Allure CLI (`allure` on `PATH`, or `npx allure-commandline` which requires Java + Node); both are optional and detected at test time.
- **Docs:** `README.md` and `AGENTS.md` gain an end-to-end testing section and Allure-CLI install guidance.
- **CI consideration:** the `npx allure-commandline` fallback downloads the package on first use (network); environments without Allure, Java, or Node simply skip the e2e test.
