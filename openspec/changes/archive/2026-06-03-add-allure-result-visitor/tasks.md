## 1. Module scaffolding

- [x] 1.1 Create `src/robotframework_allurevisitor/_convert.py` with `to_ms`, `status_of`, `status_details`, `_looks_like_error`, and `history_id` helpers (RF 7 datetime + legacy string timestamps, None-safe)
- [x] 1.2 Create `src/robotframework_allurevisitor/_labels.py` with `suite_labels(full_name)` and `tag_labels_and_links(tags, issue_pattern, link_pattern)` using `allure_commons.mapping.parse_tag`
- [x] 1.3 Replace `src/robotframework_allurevisitor/visitor.py` with a stack-based `AllureResultVisitor(ResultVisitor)` skeleton (container stack, step stack, current test) wired to `AllureFileLogger` hooks
- [x] 1.4 Update `src/robotframework_allurevisitor/__init__.py` to export `AllureResultVisitor` and `generate`

## 2. Core traversal (MVP parity)

- [x] 2.1 Implement `start_suite`/`end_suite` mapping suites to `TestResultContainer`, nesting child containers, and reporting on `end_suite`
- [x] 2.2 Implement `start_test`/`end_test` building `TestResult` (name, fullName, description, timing, status) and reporting on `end_test`; link test uuid into the owning container's `children`
- [x] 2.3 Implement `start_keyword`/`end_keyword` mapping keywords to nested `TestStepResult`, including assignment in the step name and arguments as parameters
- [x] 2.4 Apply status mapping (`status_of`) and data-derived timing (`to_ms`) to suites, tests, and steps
- [x] 2.5 Build labels: `parentSuite`/`suite`/`subSuite` from `full_name`, plus `framework`/`language`/`host` and optional `thread`
- [x] 2.6 Apply tag → label/link mapping and set stable `historyId`/`testCaseId` via `history_id`

## 3. Suite setup/teardown and control structures

- [x] 3.1 Detect suite setup/teardown keywords and record them as container `befores`/`afters` (`TestBeforeResult`/`TestAfterResult`)
- [x] 3.2 Implement control-structure hooks (`start_for`/`for_iteration`/`start_if`/`start_if_branch`/`start_while`/`start_try`/`start_try_branch` and ends) as labelled steps via shared `_push_control`/`_pop_control`
- [x] 3.3 Guard control-structure hooks with `hasattr`/try-except so pre-RF5 outputs degrade to keyword-only steps

## 4. Messages and attachments

- [x] 4.1 Implement `visit_message` to fold log messages into the owning step as HTML attachments preserving level
- [x] 4.2 Detect embedded screenshot/image references and emit binary attachments via `report_attached_file`, resolving paths relative to the `output.xml` directory

## 5. CLI and programmatic API

- [x] 5.1 Implement `generate(sources, results_dir, *, clean, thread, issue_pattern, link_pattern)` using `ExecutionResult(*sources)` native merge and the `AllureFileLogger`
- [x] 5.2 Implement the argparse CLI: positional `sources` (with glob expansion), `-o/--output`, `--clean`, `--thread`, `--issue-pattern`, `--link-pattern`
- [x] 5.3 Wrap the visit so a truncated/partial `output.xml` still flushes completed containers/results
- [x] 5.4 Update the console-script entry point and project description in `pyproject.toml`

## 6. Tests

- [x] 6.1 Decided NOT to adopt `allure-python-commons-test`; tests assert on parsed Allure JSON directly (fewer moving parts, no extra dependency)
- [x] 6.2 Golden-file parity test: run a fixture suite, convert its `output.xml`, assert statuses/labels/step tree/historyId
- [x] 6.3 Control-structure fixtures: FOR/IF/WHILE/TRY appear as steps with correct nesting and status
- [x] 6.4 Suite setup/teardown captured as container befores/afters; skipped (`robot:skip`) → skipped; library error → broken
- [x] 6.5 Multi-source merge test (`original.xml` + `rerun.xml`) yields last-wins status and stable `historyId`
- [x] 6.6 Templated/data-driven tests keep distinct logical identity via parameters in `historyId`
- [x] 6.7 Determinism test: two conversions of the same `output.xml` produce identical `historyId`/timings (uuids excluded)
- [x] 6.8 Partial-output tolerance test: a truncated `output.xml` still produces a partial report without aborting

## 7. Docs and verification

- [x] 7.1 Update `README.md` and `AGENTS.md` to document the full conversion semantics, CLI flags, and pabot/rerun/history guidance
- [x] 7.2 Run `uv run ruff check .` and `uv run pytest` and ensure all pass
