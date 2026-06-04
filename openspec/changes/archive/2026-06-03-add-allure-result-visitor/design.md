## Context

The official `allure-robotframework` adapter is a runtime Listener. It cannot regenerate results from an old run, models FOR/IF/WHILE/TRY awkwardly through keyword events, and is fragile under pabot and `--rerunfailed`+merge because the authoritative, post-merge truth lives in `output.xml` after the listeners are gone. This change adds a complementary, offline adapter that reads `output.xml` with `robot.api.ExecutionResult` + `ResultVisitor` and emits the identical Allure on-disk format by reusing `allure-python-commons`.

Current state: the repo contains a placeholder MVP visitor (`visitor.py`) covering only test→result and flat keyword→step mapping, with naive status/label handling and no containers, control structures, attachments, or merge support. This change replaces it. The research basis is `docs/research/allure-rf-output-xml-proposal.md`, which is the authoritative semantic reference. Stakeholders: CI/pabot pipeline owners and teams already using Allure Report.

## Goals / Non-Goals

**Goals:**
- Produce Allure results byte-compatible with the official adapters by reusing `allure_commons.model2` + `AllureFileLogger`.
- Correctly map suites→containers (with setup/teardown), tests→results, keywords/control-structures→nested steps.
- Derive all timing from result data (epoch ms), not wall clock; support RF 4–7.
- Achieve label/status/identity parity with the listener (`parentSuite`/`suite`/`subSuite`, severity/`allure.*` tags, stable `historyId`).
- Support multi-source native merge, pabot (`--thread`), partial-output tolerance, and a clean CLI + programmatic API.
- Single-pass, streaming traversal suitable for very large `output.xml`.

**Non-Goals:**
- Replacing the listener for live, in-run feedback (both coexist).
- Implementing Allure history/trend copying (an Allure-tooling concern; only `historyId` stability is guaranteed here).
- Re-implementing Allure JSON serialization or the Allure report generator.
- A perfect per-test thread/host reconstruction from an already-merged pabot `output.xml` (documented limitation).

## Decisions

### Reuse `allure-python-commons` model + `AllureFileLogger`
Build `TestResult`/`TestResultContainer`/`TestStepResult`/`TestBeforeResult`/`TestAfterResult` and serialize through `AllureFileLogger`. Only the traversal is new.
- *Why:* output stays compatible across Allure upgrades and matches the listener's format exactly.
- *Alternative considered:* hand-rolled JSON writer — rejected as duplicative and drift-prone.
- *Note:* the `2.16.x` `AllureFileLogger` exposes `report_result`/`report_container`/`report_attached_data`/`report_attached_file` directly. We will call these hooks directly rather than depending on `AllureReporter`'s uuid-keyed lifecycle, since we already own the model objects and build them depth-first. The dependency is pinned so this choice is stable; switching to `AllureReporter` would be a localized change because the model objects are identical either way.

### Stack-based depth-first traversal
Maintain a stack of "current executable item" (test → keyword → control → keyword) plus a stack of suite containers. Push on `start_*`, pop on `end_*`, attaching each child to `stack[-1]` (or the current test).
- *Why:* nesting becomes trivial and correct; memory is bounded by current depth, enabling streaming emit (`report_result` at `end_test`, `report_container` at `end_suite`).
- *Alternative considered:* collecting the whole tree then serializing — rejected for memory on large outputs.

### Timing from data via a single `to_ms` helper
`to_ms(value)` handles `datetime` (RF 7), legacy strings (`%Y%m%d %H:%M:%S.%f`, RF 4–6), and `None`. Prefer `start_time`/`end_time`, fall back to `starttime`/`endtime`.
- *Why:* deterministic, reproducible timings independent of conversion time; cross-version support.

### Status mapping with broken vs failed heuristic
PASS→passed; SKIP/NOT_RUN→skipped; FAIL→failed by default, →broken when the message looks like a library/import/syntax/timeout error. `StatusDetails.message` from `item.message`.
- *Why:* matches Allure's failed-vs-broken semantics and the listener's intent.
- *Risk:* the broken heuristic is message-based and imperfect (see Risks).

### Identity and labels mirror the listener
`historyId = testCaseId = md5(full_name [+ sorted params])`; suite labels split `full_name` into `parentSuite`/`suite`/`subSuite`; tags via `allure_commons.mapping.parse_tag` (severity, issue/link patterns). `framework`/`language`/`host` always; `thread` when supplied.
- *Why:* reports from the two adapters are interchangeable and Allure retry/history grouping works.

### Multi-source combine + retry grouping (not last-wins merge)
`ExecutionResult(*sources)` does **not** perform last-wins merge — verified empirically it combines sources under a synthetic root as sibling sub-suites, so both attempts of a reran test are emitted. Because `historyId = md5(full_name)` is stable, the two attempts share a `historyId` and Allure groups them as retries, showing the latest (by stop time) as the headline. This achieves last-wins *at the report level* while preserving retry history.
- *Why:* matches Allure's retry/history model and needs no extra subprocess; the research doc's claim that `ExecutionResult(*sources)` is last-wins was inaccurate.
- *For a single deduplicated result:* callers pre-merge with `rebot --merge` and pass the merged `output.xml`.
- *Pabot "don't double-count":* convert the merged file *or* the per-worker files, never both into one dir (identical `historyId` would otherwise inflate counts).

### Messages and screenshots as attachments
`visit_message` folds log messages into the owning step as HTML attachments; image references are resolved relative to the `output.xml` directory and emitted as binary attachments via `report_attached_file`.
- *Why:* keeps step logs and screenshots first-class in Allure.

### Module layout
`_convert.py` (timing/status/identity), `_labels.py` (suite/tag/link mapping), `visitor.py` (the `ResultVisitor`), `cli.py` (`generate()` + argparse). Public API in `__init__.py`: `AllureResultVisitor`, `generate`.
- *Why:* small, testable units; keeps the visitor readable.

## Risks / Trade-offs

- **Broken-vs-failed heuristic is message-based and locale/library dependent** → Keep it conservative and centralized in `_convert.status_of`; allow refinement and cover with fixtures; default to `failed` when uncertain.
- **`allure-python-commons` API surface may shift between releases** → Pin the dependency; isolate all model/logger usage behind our modules so an upgrade is a localized change.
- **Merged pabot `output.xml` loses per-worker attribution** → Document both strategies; offer `--thread` + per-worker conversion when the Timeline view matters; warn against mixing strategies (identical `historyId` would inflate counts).
- **RF version differences in control-structure hooks (pre-5) and timestamp types** → Guard hooks with `hasattr`/try-except so older outputs degrade to keyword-only steps; `to_ms` handles both timestamp forms; validate against an RF 5/6/7 matrix.
- **Truncated `output.xml`** → Wrap the visit so completed containers/results are still flushed, yielding a partial report rather than nothing.
- **Templated/data-driven tests share names** → Fold templated-keyword args into `parameters` and `historyId` so logical cases stay distinct; identical name+args across reruns intentionally shares `historyId` for retry grouping.

## Migration Plan

1. Replace the placeholder `visitor.py`/`cli.py` and add `_convert.py`/`_labels.py`; update `__init__.py` exports and the `pyproject.toml` console script.
2. Land MVP parity (suites/tests/keywords, status/timing/labels/tags, CLI) with golden-file tests vs the listener for simple suites.
3. Add control structures, suite setup/teardown containers, messages/screenshots attachments.
4. Add pabot, rerun/merge, templated-test, and RF 5/6/7 fixtures; document history usage.

Rollback: the change is additive to consumers (Allure output format unchanged) and the listener remains available; reverting the package commits restores the prior MVP with no external migration.

## Open Questions

- Should `--thread`/`host` be auto-derived when converting per-worker pabot files (e.g. from the directory name), or always explicit? (Lean: explicit via flag for MVP.)
- Do we adopt `allure-python-commons-test` hamcrest matchers as a dev dependency for golden-file assertions, or assert on parsed JSON directly? (Lean: add the matcher lib to the dev group for expressiveness.)
- Exact set of substrings used by the broken-vs-failed heuristic — to be finalized against real fixtures.
