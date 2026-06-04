## Context

The existing tests (`tests/test_visitor.py`) stop at asserting the emitted Allure JSON. The actual consumer is the Allure report generator, which validates and renders those files. Without an end-to-end test, format incompatibilities only surface when a user runs `allure generate`. This change adds a real pipeline test: Robot run → `rf-allure` (subprocess) → Allure report → assertions on the report.

Environment constraints (verified): there is **no `allure` binary on PATH**, but **Java and Node/npx are present**, so `npx allure-commandline` (a Java-backed npm wrapper of the same generator) can produce a report here. The report generator is inherently an external, Java-based tool — there is no pure-Python Allure report generator — so the test must tolerate its absence.

## Goals / Non-Goals

**Goals:**
- Prove the converter's output is consumable by the real Allure generator and yields a statistically-correct report.
- Exercise the packaged `rf-allure` console script (subprocess), not just the in-process `generate`.
- Stay green and fast on machines without an Allure CLI (graceful skip), while actually generating a report wherever a generator is resolvable.
- Cover a realistic mix (passed/failed/skipped/broken, tags, setup/teardown, control structures, an attachment) so report widgets are meaningfully checked.

**Non-Goals:**
- Bundling or installing the Allure CLI as a project dependency.
- Asserting on rendered HTML/visual layout — we assert on the report's machine-readable data (`summary.json`, `data/test-cases/`), which is stable across Allure versions.
- Pixel/screenshot verification or browser automation.
- Allure history/trend across runs (covered conceptually elsewhere; out of scope here).

## Decisions

### Resolve the generator, don't require it
A helper returns a command prefix for report generation: `allure` if `shutil.which("allure")`, else `["npx", "--yes", "allure-commandline"]` when both `node` and `java` are present, else `None`. `None` → `pytest.skip(...)`.
- *Why:* maximizes the chance the report step actually runs (it runs here via npx) while keeping the suite portable. A bare "require allure on PATH" would skip in this very environment, defeating the purpose.
- *Alternative considered:* hard-require `allure` (rejected: always skips here); download the standalone generator in-test (rejected: heavier, version pinning, slower).

### Generate via `allure generate --clean -o <report> <results>`
Both `allure` and `allure-commandline` accept the same `generate` subcommand and flags.
- *Why:* one code path for both resolutions; `--clean` keeps the test idempotent.

### Convert via the `rf-allure` subprocess
The e2e test shells out to the installed `rf-allure` console script for the conversion step.
- *Why:* exercises the packaging/entry point and the exact path a user takes, distinct from the unit tests that call `generate()` in-process.

### Assert on report data, not HTML
Check `report/index.html` exists; parse `report/widgets/summary.json` and compare its `statistic` counts to the suite's known counts; count files in `report/data/test-cases/`.
- *Why:* `summary.json`/`data` are the report's stable, machine-readable contract; HTML structure changes across Allure versions and is brittle to assert on.
- *Risk:* `summary.json` shape could vary by Allure major version → read defensively (`.get`), assert the counts we rely on, and skip with a clear message if the schema is unrecognized.

### `e2e` marker, registered, default-on, self-skipping
Register `e2e` in `pyproject.toml` `[tool.pytest.ini_options].markers`; tag the test `@pytest.mark.e2e`. It runs by default but skips when no generator is resolvable.
- *Why:* lets CI run `-m "not e2e"` for a hermetic fast lane and `-m e2e` for the full check, without unregistered-marker warnings.

### Representative fixture suite
One suite file with: a passing test (tags incl. `allure.severity:critical`), a failing assertion, a `robot:skip` test, a broken test (unknown keyword), suite Setup/Teardown, and a FOR/IF block with a logged message.
- *Why:* drives all four status buckets so `summary.json` is a real check, and exercises containers/steps/attachments through the generator.

## Risks / Trade-offs

- **`npx allure-commandline` downloads on first run (network + time)** → Acceptable for an opt-in/e2e lane; the test has a generous subprocess timeout and skips (not fails) if the generator cannot be obtained or errors out for environmental reasons. Document the one-time cost.
- **Allure version drift in `summary.json`/`data` layout** → Assert only on stable fields read defensively; fall back to skip-with-message if the expected files are absent.
- **Broken-status mapping depends on Robot's error message text** → The fixture uses an unknown-keyword failure, whose message reliably triggers the `broken` heuristic (already covered by unit tests); if Robot changes the wording, the unit test catches it first.
- **Flaky network/CI** → Keep the e2e test isolated in its own file and marker so it can be excluded from the fast lane.
- **Subprocess slowness** → One Robot run + one conversion + one report generation per e2e test; keep the fixture small but representative.

## Migration Plan

1. Add the resolver + `e2e` skip helper and register the marker in `pyproject.toml`.
2. Add the fixture suite and `tests/test_e2e_report.py`.
3. Run locally: with no `allure` on PATH it should resolve `npx allure-commandline`, generate a report, and pass; if npx cannot fetch the package, it skips cleanly.
4. Update docs.

Rollback: the change is test-only and additive — deleting `test_e2e_report.py`, the helper, and the marker entry reverts it with no impact on the library or its consumers.

## Open Questions

- Should the e2e test be excluded from the default `pytest` run entirely (opt-in via `-m e2e`) rather than default-on-self-skip? (Lean: default-on-self-skip, so it provides value locally and in CI lanes that have Java+Node, with zero failures elsewhere.)
- Pin a specific `allure-commandline` version for reproducibility, or always use latest? (Lean: latest for now; revisit if version drift breaks assertions.)
