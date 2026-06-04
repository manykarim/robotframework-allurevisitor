## 1. Test infrastructure

- [x] 1.1 Register an `e2e` marker in `pyproject.toml` `[tool.pytest.ini_options].markers`
- [x] 1.2 Add an Allure-CLI resolver helper to `tests/conftest.py`: return `["allure"]` if on `PATH`, else `["npx", "--yes", "allure-commandline"]` when both `node` and `java` are present, else `None`
- [x] 1.3 Add a helper that generates a report via `<resolver> generate --clean -o <report> <results>` and a pytest skip when the resolver is `None`

## 2. Fixture suite

- [x] 2.1 Add a representative Robot suite covering passed (with `allure.severity:critical` and a `feature` tag), failed (assertion), skipped (`robot:skip`), and broken (unknown keyword) tests, plus Suite Setup/Teardown and a FOR/IF block that logs a message

## 3. End-to-end test

- [x] 3.1 Create `tests/test_e2e_report.py` with an `@pytest.mark.e2e` test that runs the fixture suite to `output.xml`
- [x] 3.2 Convert `output.xml` by invoking the installed `rf-allure` console script as a subprocess into an `allure-results` directory
- [x] 3.3 Generate an Allure report from the results using the resolver helper
- [x] 3.4 Assert `report/index.html` exists
- [x] 3.5 Parse `report/widgets/summary.json` and assert its `statistic` counts match the fixture's passed/failed/skipped/broken counts (read defensively; skip with a clear message if the schema is unrecognized)
- [x] 3.6 Assert `report/data/test-cases/` contains one entry per executed test

## 4. Docs and verification

- [x] 4.1 Document the end-to-end flow, the `e2e` marker (`-m e2e` / `-m "not e2e"`), and Allure-CLI install options in `README.md` and `AGENTS.md`
- [x] 4.2 Run `uv run ruff check .` and `uv run pytest`; confirm the e2e test either passes (report generated) or skips cleanly, and all other tests pass
