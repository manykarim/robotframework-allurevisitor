## Why

The official `allure-robotframework` package is a runtime Listener: it only describes the single live run it observed, cannot regenerate results from an old run, and handles pabot/parallel execution and `--rerunfailed` merges poorly because the authoritative, merged truth lives in `output.xml` *after* the listeners are gone. We need a complementary, offline adapter that reads `output.xml` post-execution and emits the exact same Allure result format, so CI, pabot, and rerun/merge pipelines have a canonical, re-runnable Allure generator. The current repo contains only a throwaway MVP visitor that lacks containers, control structures, attachments, merge handling, and correct label/status semantics.

## What Changes

- Replace the placeholder MVP visitor with a stack-based `ResultVisitor` that walks `robot.api.ExecutionResult` and emits Allure `*-result.json`, `*-container.json`, and `*-attachment.*` files via the official `allure-python-commons` model and `AllureFileLogger` (byte-compatible output).
- Map RF suites → `TestResultContainer` (with suite setup/teardown as `befores`/`afters`), tests → `TestResult`, keywords and control structures (FOR/IF/WHILE/TRY/GROUP/VAR) → nested `TestStepResult`.
- Derive all `start`/`stop` timestamps from RF's `start_time`/`end_time` (epoch ms), never wall-clock; support RF 7 `datetime` and legacy RF 4–6 string timestamps.
- Map status correctly (PASS→passed, SKIP/NOT_RUN→skipped, FAIL→failed, library/syntax errors→broken) with `StatusDetails`.
- Emit labels parity with the listener: `parentSuite`/`suite`/`subSuite` from `full_name`, `framework`/`language`/`host`/`thread`, severity, and `allure.*` tag → label/link mapping via `parse_tag`; stable `historyId`/`testCaseId = md5(full_name [+ params])`.
- Fold RF log messages into the owning step as HTML attachments; resolve embedded screenshots to first-class binary attachments.
- **BREAKING** (pre-1.0, internal): the CLI entry point and programmatic API are redefined — `generate(sources, results_dir, ...)` accepts one or many `output.xml` sources (native RF merge / last-wins), plus `--clean`, `--thread`, `--issue-pattern`, `--link-pattern` flags. The console script is renamed/clarified accordingly.
- Document and support pabot (merged vs per-worker strategies), `--rerunfailed`+merge, data-driven/templated tests, partial/corrupt `output.xml` tolerance, and Allure history across runs.

## Capabilities

### New Capabilities
- `allure-result-generation`: Traverse a Robot Framework result tree and produce semantically-correct Allure result/container/step model objects — status mapping, data-derived timing, suite→container nesting with setup/teardown, keyword and control-structure steps, label/tag/link mapping, stable identity, and message/screenshot attachments — written to disk via the official Allure file logger.
- `allure-conversion-cli`: A command-line and programmatic interface to convert one or more `output.xml` sources into an Allure results directory, supporting native multi-source merge, clean output, thread labelling, issue/link patterns, and tolerance of partial output.

### Modified Capabilities
<!-- None: no existing specs. -->

## Impact

- **Code:** rewrites `src/robotframework_allurevisitor/visitor.py` and `cli.py`; adds internal helper modules (timing/status/identity conversion, label/tag mapping); updates `src/robotframework_allurevisitor/__init__.py` public API.
- **Packaging:** `pyproject.toml` console-script entry point and project description; no new required runtime dependencies (already `robotframework` + `allure-python-commons`).
- **Tests:** expands `tests/` with golden-file parity, control-structure, pabot, rerun/merge, templated-test, and RF version-matrix fixtures (dev group: `pytest`; optionally `allure-python-commons-test` matchers).
- **Docs:** `README.md` and `AGENTS.md` updated to reflect the full conversion semantics and CLI.
- **Consumers:** Allure Report / `allure generate` consume the output unchanged; complements (does not remove) the existing listener.
