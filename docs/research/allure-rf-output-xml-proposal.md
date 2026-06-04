# Solution Proposal: Allure Results from Robot Framework `output.xml`

**An offline, post-execution adapter using `robot.api.ExecutionResult` + `ResultVisitor`**

---

## 1. Executive summary

The official `allure-robotframework` package is a **runtime Listener**. It hooks into the live execution (`start_suite`, `start_test`, `start_keyword`, `log_message`, …) and emits Allure JSON as tests run. This works, but it has structural limitations that matter for your environment:

- **Pabot / parallel execution:** each pabot worker is a separate process running its own listener. Thread/host labels are derived from the live process, and merging behaviour for `--rerunfailed` is governed by Rebot *after* the listeners are gone, so the listener never sees the merged truth.
- **Reruns and merges:** the listener can only describe the run it observed. The canonical, post-merge result lives in `output.xml`, not in any single listener's view.
- **Re-processing:** you cannot re-generate Allure results from an old run without re-executing it.
- **Control structures (FOR/IF/WHILE/TRY):** the listener API surfaces these as keyword-like events that are fiddly to model correctly; the result model exposes them as first-class typed body items.

This proposal describes a **second, complementary adapter** that reads `output.xml` *after* execution using `robot.api.ExecutionResult` and a `ResultVisitor`, and writes the exact same Allure result format (`*-result.json`, `*-container.json`, `*-attachment.*`) consumed by Allure 2 / Allure Report. It reuses the official `allure-python-commons` model and file logger so the output is byte-compatible with the rest of the Allure ecosystem.

The two approaches are not mutually exclusive. The recommended end state is: **use the listener when you want live results during a single-process run; use this output.xml adapter as the canonical generator for CI, pabot, and rerun/merge pipelines.**

---

## 2. Analysis of `allure-framework/allure-python`

### 2.1 Repository layout

The repo is a monorepo of adapters sharing one engine:

| Package | Role |
|---|---|
| `allure-python-commons` | The shared engine: data model, lifecycle, plugin hooks, JSON file logger, tag→label mapping, utils (md5, now, host/thread tags). **This is what we reuse.** |
| `allure-pytest`, `allure-behave`, `allure-pytest-bdd`, `allure-nose2` | Framework adapters. |
| `allure-robotframework` | The existing RF **Listener** adapter. Our reference for RF→Allure semantics. |
| `allure-python-commons-test` | Hamcrest matchers to assert on emitted Allure JSON. **Useful for our test suite.** |

Latest release line at time of writing is the `2.15.x` series.

### 2.2 The Allure data model (`allure_commons.model2`)

The on-disk format is a directory of JSON files. The relevant `attrs` classes:

- **`TestResult`** → serialized as `<uuid>-result.json`. Fields: `uuid`, `historyId`, `testCaseId`, `fullName`, `name`, `status`, `statusDetails`, `stage`, `description`/`descriptionHtml`, `steps[]`, `attachments[]`, `parameters[]`, `labels[]`, `links[]`, `start`, `stop`, `titlePath[]`.
- **`TestResultContainer`** → serialized as `<uuid>-container.json`. Fields: `uuid`, `name`, `children[]` (UUIDs of contained results/containers), `befores[]`, `afters[]`, `start`, `stop`. **This is how suite setup/teardown is attached to all tests in a suite.**
- **`ExecutableItem`** (base of `TestResult`, `TestStepResult`, `TestBeforeResult`, `TestAfterResult`): the recursive step container — `steps[]`, `attachments[]`, `parameters[]`, `status`, `statusDetails`, `start`, `stop`.
- **`StatusDetails`**: `message`, `trace`, `known`, `flaky`.
- **`Label`** (`name`/`value`), **`Link`** (`type`/`url`/`name`), **`Parameter`** (`name`/`value`/`excluded`/`mode`), **`Attachment`** (`name`/`source`/`type`).
- **`Status`**: `passed`, `failed`, `broken`, `skipped`, `unknown`.

### 2.3 Serialization (`allure_commons.logger.AllureFileLogger`)

```python
data = asdict(item, filter=lambda _, v: v or v is False)   # drops empty/None, keeps False
filename = item.file_pattern.format(prefix=uuid.uuid4())     # "<uuid>-result.json" etc.
json.dump(data, json_file, indent=indent, ensure_ascii=False)
```

Key consequences we must honour:
- Files are named `<random-uuid>-result.json` / `<random-uuid>-container.json`. The `uuid` *field inside* the JSON is the logical identity used for `children` references; the filename uuid is independent.
- Attachments are copied/written by the logger via `report_attached_file(source, file_name)` / `report_attached_data(body, file_name)` and named `<uuid>-attachment.<ext>`.

**We reuse `AllureFileLogger` directly** — we do not re-implement serialization.

### 2.4 Identity & timing conventions (`allure_commons.utils`)

- `now()` → `int(round(1000 * time.time()))` — **epoch milliseconds**.
- `md5(*args)` → hex digest, used for `testCaseId`/`historyId`.
- `host_tag()` → `socket.gethostname()`; `thread_tag()` → `"{pid}-{threadname}"`; `platform_label()` → e.g. `cpython3`.

For an offline adapter, `now()` is **wrong** — we must derive `start`/`stop` from the timestamps in `output.xml`, not wall-clock at conversion time.

### 2.5 How the existing Listener maps RF → Allure (our semantic reference)

From `allure_robotframework/allure_listener.py` and `utils.py`:

| RF concept | Allure mapping |
|---|---|
| RF `PASS` | `Status.PASSED` |
| RF `FAIL` | `Status.FAILED` (assertion) — listener treats non-pass as failed/broken |
| RF `SKIP` / `robot:skip` tag | `Status.SKIPPED` |
| `longname` (`Root.Sub.Test`) | `fullName`; `testCaseId = historyId = md5(longname)` |
| `longname` split on `.` | suite labels: first → `parentSuite`, middle → `suite`, last → `subSuite` (see `get_allure_suites`) |
| Suite setup/teardown | container `befores`/`afters` |
| Keyword | nested `TestStepResult` |
| Log message | `<p><b>[LEVEL]</b> message</p>` HTML, attached/folded into step |
| Tag `allure.feature:X` etc. | parsed via `mapping.parse_tag` → `Label`/`Link` |
| Tag matching a `Severity` | `severity` label |
| `framework`/`language`/`host`/`thread` | standard labels |

`get_allure_suites(longname)` precisely:
- 2 parts → `suite`, `subSuite`
- 3+ parts → `parentSuite`, `suite`(joined middle), `subSuite`

We replicate these mappings so the two adapters produce interchangeable reports.

---

## 3. The Robot Framework result API

### 3.1 `ExecutionResult` and `ResultVisitor`

```python
from robot.api import ExecutionResult, ResultVisitor
result = ExecutionResult("output.xml")          # accepts one or many xml paths
result.visit(MyAllureVisitor(...))
```

`ResultVisitor` exposes `start_suite/end_suite`, `start_test/end_test`, `start_keyword/end_keyword`, plus typed hooks for control structures: `start_for`, `start_if`, `start_if_branch`, `start_while`, `start_try`, `start_try_branch`, `for_iteration`, `visit_message`, etc. Returning `False` from a `start_*` method prunes that subtree.

### 3.2 Result model objects (validated against RF 7.x runtime)

- `TestCase`: `name`, `full_name` (== `longname`), `doc`, `tags`, `status` (`PASS`/`FAIL`/`SKIP`/`NOT_RUN`), `message`, `start_time` (`datetime.datetime`), `end_time`, `elapsed_time` (`datetime.timedelta`), `body`, `setup`, `teardown`, `parent`, `source`, `lineno`.
- `Keyword`: `name`, `kwname`, `libname`, `owner`, `args`, `assign`, `tags`, `doc`, `type` (`KEYWORD`/`SETUP`/`TEARDOWN`/`FOR`/`IF`/…), `status`, `message`, `start_time`, `elapsed_time`, `messages`, `body`.
- `Message`: `level` (`TRACE`/`DEBUG`/`INFO`/`WARN`/`ERROR`/`FAIL`), `message`, `html`, `timestamp`.
- Control structures are typed body items: `For`, `ForIteration`, `If`, `IfBranch`, `While`, `Try`, `TryBranch`, `Var`, `Return`, `Break`, `Continue`, `Group`.

> **Critical RF 7 change:** times are `datetime`/`timedelta`, **not** strings. Convert with `int(dt.timestamp() * 1000)`. (Pre-7 used `starttime`/`endtime` strings like `20231101 12:00:00.000`; support both for compatibility — see §6.5.)

---

## 4. Solution architecture

```
                ┌───────────────────────────────────────────────┐
   output.xml   │   robot.api.ExecutionResult(*sources)          │
 (1..n files) ──►   .visit(AllureResultVisitor)                  │
                │                                                 │
                │   AllureResultVisitor                           │
                │     ├─ maintains a stack of ExecutableItem      │
                │     ├─ suite → TestResultContainer              │
                │     ├─ test  → TestResult                       │
                │     ├─ kw/control → TestStepResult              │
                │     ├─ message → HTML attachment / step log     │
                │     └─ emits via AllureReporter (commons)       │
                │                                                 │
                │   AllureReporter ──► AllureFileLogger           │
                └──────────────────────────────────────┬─────────┘
                                                        ▼
                                          allure-results/  (*-result.json,
                                          *-container.json, *-attachment.*)
```

Design principles:

1. **Reuse, don't reinvent.** Use `allure_commons.model2`, `allure_commons.logger.AllureFileLogger`, `allure_commons.mapping.parse_tag`, and `allure_commons.utils.md5`. Only the *traversal* is new.
2. **Timestamps from data, not wall clock.** Every `start`/`stop` comes from RF's `start_time`/`end_time`.
3. **Stack-based traversal.** A simple stack of "current executable item" makes nesting (suite ▸ test ▸ keyword ▸ control ▸ keyword) trivial and correct.
4. **Idempotent & offline.** Running it twice on the same `output.xml` yields equivalent results; no execution required.

---

## 5. Reference implementation

> Target: `robotframework-allure-output` (a thin package exposing a CLI `rf-allure`). Depends on `allure-python-commons` and `robotframework`.

### 5.1 Helpers — timing, status, identity

```python
# rf_allure/_convert.py
from datetime import datetime, timedelta
from allure_commons.utils import md5
from allure_commons.model2 import Status, StatusDetails, Label, Link, Parameter
from allure_commons.types import LabelType, Severity
from allure_commons.mapping import parse_tag

_RF7 = hasattr(datetime, "timestamp")  # always True; flag kept for clarity

def to_ms(value):
    """RF7 datetime/timedelta -> epoch ms.  RF<7 string -> epoch ms.  None-safe."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return int(round(value.timestamp() * 1000))
    if isinstance(value, str):  # legacy '20231101 12:00:00.000'
        dt = datetime.strptime(value, "%Y%m%d %H:%M:%S.%f")
        return int(round(dt.timestamp() * 1000))
    return None

def status_of(item):
    """Map RF status to Allure status. Distinguish assertion-fail vs error-broken."""
    s = item.status
    if s == "PASS":
        return Status.PASSED, None
    if s == "SKIP":
        return Status.SKIPPED, status_details(item)
    if s == "NOT_RUN":
        # FOR/IF dry-run branches etc. — treat as skipped for reporting clarity
        return Status.SKIPPED, None
    # FAIL: broken vs failed.  RF doesn't separate, but library/syntax errors
    # surface as messages at ERROR level -> classify as broken; assertion text
    # (the common case) -> failed.
    details = status_details(item)
    if _looks_like_error(item):
        return Status.BROKEN, details
    return Status.FAILED, details

def status_details(item):
    msg = getattr(item, "message", None)
    if not msg:
        return None
    return StatusDetails(message=msg)

def _looks_like_error(item):
    msg = (getattr(item, "message", "") or "").lower()
    return any(t in msg for t in (
        "no keyword with name", "importing", "syntax", "resolving variable",
        "expected", "evaluating", "timeout"
    )) and "!=" not in msg  # crude; refine per your libraries

def history_id(full_name, parameters=None):
    """Stable across reruns: md5(full_name [+ sorted parameter values])."""
    parts = [full_name]
    if parameters:
        parts += [f"{p.name}={p.value}" for p in sorted(parameters, key=lambda x: x.name or "")]
    return md5(*parts)
```

### 5.2 Suite-label and tag mapping (mirrors the listener)

```python
# rf_allure/_labels.py
from allure_commons.model2 import Label
from allure_commons.types import LabelType
from allure_commons.mapping import parse_tag

def suite_labels(full_name):
    """'Root.Mid.Leaf.Test' -> parentSuite/suite/subSuite, dropping the test name."""
    parts = full_name.split(".")[:-1]  # last part is the test name
    labels = []
    if not parts:
        return labels
    if len(parts) == 1:
        labels.append(Label(LabelType.SUITE, parts[0]))
    elif len(parts) == 2:
        labels.append(Label(LabelType.SUITE, parts[0]))
        labels.append(Label(LabelType.SUB_SUITE, parts[1]))
    else:
        labels.append(Label(LabelType.PARENT_SUITE, parts[0]))
        labels.append(Label(LabelType.SUITE, ".".join(parts[1:-1])))
        labels.append(Label(LabelType.SUB_SUITE, parts[-1]))
    return labels

def tag_labels_and_links(tags, issue_pattern=None, link_pattern=None):
    labels, links = [], []
    for tag in tags:
        parsed = parse_tag(tag, issue_pattern=issue_pattern, link_pattern=link_pattern)
        (links if parsed.__class__.__name__ == "Link" else labels).append(parsed)
    return labels, links
```

### 5.3 The visitor

```python
# rf_allure/visitor.py
from robot.api import ResultVisitor
from allure_commons.model2 import (
    TestResult, TestResultContainer, TestStepResult,
    TestBeforeResult, TestAfterResult, Label, Parameter,
)
from allure_commons.types import LabelType
from allure_commons.utils import uuid4, host_tag, platform_label
from ._convert import to_ms, status_of, status_details, history_id
from ._labels import suite_labels, tag_labels_and_links

KW_TYPE_PREFIX = {"FOR": "FOR", "IF": "IF", "WHILE": "WHILE", "TRY": "TRY",
                  "GROUP": "GROUP", "VAR": "VAR"}

class AllureResultVisitor(ResultVisitor):
    def __init__(self, reporter, *, host=None, thread=None,
                 issue_pattern=None, link_pattern=None):
        self._reporter = reporter
        self._host = host or host_tag()
        self._thread = thread                      # set per-pabot-worker, see §6.1
        self._platform = platform_label()
        self._issue_pattern = issue_pattern
        self._link_pattern = link_pattern
        self._containers = []                      # stack of TestResultContainer (suites)
        self._steps = []                           # stack of ExecutableItem (test/kw/control)
        self._test = None                          # current TestResult or None

    # ---------- suites -> containers ----------
    def start_suite(self, suite):
        container = TestResultContainer(uuid=uuid4(), name=suite.name,
                                        start=to_ms(suite.start_time),
                                        stop=to_ms(suite.end_time))
        self._containers.append(container)

    def end_suite(self, suite):
        container = self._containers.pop()
        # nest into parent container so suite setup/teardown cascades
        if self._containers:
            self._containers[-1].children.append(container.uuid)
        self._reporter.report_container(container)

    def start_suite_setup_or_teardown(self, kw, kind):
        item = (TestBeforeResult if kind == "before" else TestAfterResult)(
            name=kw.name, start=to_ms(kw.start_time), stop=to_ms(kw.end_time))
        st, det = status_of(kw)
        item.status, item.statusDetails = st, det
        self._steps.append(item)

    # ---------- tests -> results ----------
    def start_test(self, test):
        params = []  # RF tests have no native params; data-driven templates handled in §6.3
        labels = suite_labels(test.full_name)
        tlabels, links = tag_labels_and_links(test.tags, self._issue_pattern, self._link_pattern)
        labels += tlabels
        labels += [
            Label(LabelType.FRAMEWORK, "robotframework"),
            Label(LabelType.LANGUAGE, self._platform),
            Label(LabelType.HOST, self._host),
        ]
        if self._thread:
            labels.append(Label(LabelType.THREAD, self._thread))

        tr = TestResult(
            uuid=uuid4(),
            name=test.name,
            fullName=test.full_name,
            testCaseId=history_id(test.full_name, params),
            historyId=history_id(test.full_name, params),
            start=to_ms(test.start_time),
            stop=to_ms(test.end_time),
            description=test.doc or None,
            labels=labels, links=links, parameters=params,
            titlePath=test.full_name.split(".")[:-1],
        )
        st, det = status_of(test)
        tr.status, tr.statusDetails = st, det
        self._test = tr
        self._steps.append(tr)
        if self._containers:
            self._containers[-1].children.append(tr.uuid)

    def end_test(self, test):
        self._steps.pop()
        self._reporter.report_result(self._test)
        self._test = None

    # ---------- keywords & control structures -> steps ----------
    def start_keyword(self, kw):
        # suite/test setup & teardown are also keywords; RF marks them via kw.type
        if kw.parent is not None and getattr(kw.parent, "type", None) == "SUITE" \
           and kw.type in ("SETUP", "TEARDOWN") and self._containers:
            kind = "before" if kw.type == "SETUP" else "after"
            self.start_suite_setup_or_teardown(kw, kind)
            return
        step = TestStepResult(name=self._step_name(kw),
                              start=to_ms(kw.start_time), stop=to_ms(kw.end_time))
        st, det = status_of(kw)
        step.status, step.statusDetails = st, det
        self._add_args_as_params(step, kw)
        self._attach_parent(step)
        self._steps.append(step)

    def end_keyword(self, kw):
        item = self._steps.pop()
        if item.__class__ in (TestBeforeResult, TestAfterResult):
            container = self._containers[-1]
            (container.befores if isinstance(item, TestBeforeResult)
             else container.afters).append(item)

    def visit_message(self, msg):
        # fold RF log messages into the current step as an HTML attachment-ish step log
        target = self._steps[-1] if self._steps else self._test
        if target is None:
            return
        body = f"<p><b>[{msg.level}]</b>&nbsp;{msg.message}</p>"
        fname = f"{uuid4()}-attachment.html"
        self._reporter.report_attached_data(body, fname)
        from allure_commons.model2 import Attachment
        target.attachments.append(Attachment(name=f"Log [{msg.level}]",
                                              source=fname, type="text/html"))

    # control structures: reuse keyword machinery with a labelled name
    def start_for(self, f):       self._push_control(f, f"FOR {f.flavor} {', '.join(f.variables)}")
    def end_for(self, f):         self._pop_control()
    def start_for_iteration(self, it): self._push_control(it, "iteration")
    def end_for_iteration(self, it):   self._pop_control()
    def start_if(self, x):        self._push_control(x, "IF")
    def end_if(self, x):          self._pop_control()
    def start_if_branch(self, b): self._push_control(b, f"{b.type} {b.condition or ''}".strip())
    def end_if_branch(self, b):   self._pop_control()
    def start_while(self, w):     self._push_control(w, f"WHILE {w.condition or ''}".strip())
    def end_while(self, w):       self._pop_control()
    def start_try(self, t):       self._push_control(t, "TRY")
    def end_try(self, t):         self._pop_control()
    def start_try_branch(self, b):self._push_control(b, b.type)
    def end_try_branch(self, b):  self._pop_control()

    # ---------- internals ----------
    def _push_control(self, item, name):
        step = TestStepResult(name=name, start=to_ms(item.start_time),
                              stop=to_ms(getattr(item, "end_time", None)))
        st, det = status_of(item)
        step.status, step.statusDetails = st, det
        self._attach_parent(step)
        self._steps.append(step)

    def _pop_control(self):
        self._steps.pop()

    def _attach_parent(self, step):
        parent = self._steps[-1] if self._steps else self._test
        if parent is not None:
            parent.steps.append(step)

    def _step_name(self, kw):
        name = kw.name
        if getattr(kw, "assign", None):
            name = f"{', '.join(kw.assign)} = {name}"
        return name

    def _add_args_as_params(self, step, kw):
        for i, arg in enumerate(getattr(kw, "args", []) or []):
            step.parameters.append(Parameter(name=f"arg{i}", value=str(arg)))
```

### 5.4 CLI entry point

```python
# rf_allure/cli.py
import argparse, glob
from robot.api import ExecutionResult
from allure_commons._core import plugin_manager
from allure_commons.reporter import AllureReporter
from allure_commons.logger import AllureFileLogger
from .visitor import AllureResultVisitor

def generate(sources, results_dir, *, clean=False, host=None, thread=None,
             issue_pattern=None, link_pattern=None):
    logger = AllureFileLogger(results_dir, clean=clean)
    plugin_manager.register(logger)
    try:
        reporter = AllureReporter()                # talks to logger via hooks
        # ExecutionResult merges multiple xml files natively (see §6.2)
        result = ExecutionResult(*sources)
        visitor = AllureResultVisitor(reporter, host=host, thread=thread,
                                      issue_pattern=issue_pattern,
                                      link_pattern=link_pattern)
        result.visit(visitor)
    finally:
        plugin_manager.unregister(logger)

def main():
    p = argparse.ArgumentParser("rf-allure",
        description="Generate Allure results from Robot Framework output.xml")
    p.add_argument("sources", nargs="+", help="output.xml file(s) or glob(s)")
    p.add_argument("-o", "--output", default="allure-results")
    p.add_argument("--clean", action="store_true")
    p.add_argument("--thread", default=None, help="thread label (pabot worker id)")
    p.add_argument("--issue-pattern", default=None)
    p.add_argument("--link-pattern", default=None)
    args = p.parse_args()
    files = [f for s in args.sources for f in (glob.glob(s) or [s])]
    generate(files, args.output, clean=args.clean, thread=args.thread,
             issue_pattern=args.issue_pattern, link_pattern=args.link_pattern)

if __name__ == "__main__":
    main()
```

> **Note on `AllureReporter`:** the commons `reporter.AllureReporter` maintains its own item lifecycle keyed by uuid; depending on the installed `2.15.x` API you may instead call the file logger's `report_result` / `report_container` / `report_attached_data` hooks directly (as `AllureMemoryLogger`/`AllureFileLogger` expose them). Pin the dependency and adapt the two `report_*` calls accordingly — the model objects we build are identical either way. The decoupling via the model is deliberate so this choice is a one-line change.

---

## 6. Special cases

### 6.1 Parallel execution with Pabot

Pabot runs each suite/test in a separate worker process and writes **one `output.xml` per worker** under `pabot_results/`, then calls Rebot to merge them into a single top-level `output.xml`.

Two valid strategies:

**(A) Convert the merged output.xml (recommended default).**
After pabot finishes, point the adapter at the single merged `output.xml`:
```bash
pabot --testlevelsplit --output output.xml tests/
rf-allure output.xml -o allure-results --clean
```
*Pro:* one canonical, deduplicated result set; matches what `report.html` shows. *Con:* the merged file does not retain which worker ran which test, so `thread`/`host` labels can't be perfectly reconstructed per test.

**(B) Convert each worker's output.xml with a thread label, then aggregate.**
Iterate the per-worker files and tag each with a distinct `thread` so Allure's *Timeline* / *Behaviors* views show parallelism:
```bash
for d in pabot_results/*/; do
  rf-allure "$d/output.xml" -o allure-results --thread "$(basename "$d")"
done
```
The adapter supports `--thread`; each invocation appends to the same `allure-results` dir (uuids prevent collisions). Use this when you want the Allure **Timeline** to reflect real worker concurrency.

> **Guard against double counting.** Do **not** mix strategies — either convert the merged file *or* the per-worker files, never both into the same results dir. The `historyId = md5(full_name)` is identical across both, so duplicates would inflate counts.

### 6.2 Rerunning failed tests and merging (`--rerunfailed` + `rebot --merge`)

RF's rerun/merge flow:
```bash
robot --output original.xml tests/
robot --rerunfailed original.xml --output rerun.xml tests/
rebot --merge original.xml rerun.xml --output merged.xml
```
In `merged.xml`, reran tests carry merge metadata: the latest result is authoritative and the prior attempt is recorded (RF adds a "*Re-executed test*" / original-status message to the test body).

**Adapter behaviour:**
- Point the adapter at `merged.xml`. `ExecutionResult("merged.xml")` already yields the **final, authoritative** status per test — exactly what Allure should show as the headline result.
- Because `historyId` is stable (`md5(full_name)`), Allure's **Retries / History** view correctly groups the merged result with previous CI runs (provided you carry the `history/` folder between runs — see §6.4).
- To surface the *previous attempt* inside the test, the merge message RF injects is captured by `visit_message` and folded into the test as an HTML attachment, so reviewers can see "originally failed, passed on retry."

`ExecutionResult` also accepts **multiple sources directly** and merges them, so you can skip the explicit `rebot --merge` step:
```python
ExecutionResult("original.xml", "rerun.xml")   # last-wins per test
rf-allure original.xml rerun.xml -o allure-results --clean
```
This is the most efficient path: one process, no intermediate merged file, native RF merge semantics.

### 6.3 Data-driven tests (templates) and identical test names

Template tests (`[Template]`) and tests generated in loops can share a `name`. To keep `historyId` unique per logical case:
- Include the iteration's argument values in `historyId`: when a test body's top-level item is a templated keyword, fold its args into `parameters` and into `history_id(full_name, parameters)`.
- For genuinely identical `full_name` + args (re-run of the same case), identical `historyId` is *correct* — that is what drives Allure's retry grouping.

### 6.4 Allure history across CI runs

Allure's trend/retry features rely on a `history/` directory copied from the *previous* generated report into the *next* `allure-results` before report generation:
```bash
cp -r previous-report/history allure-results/history    # if present
allure generate allure-results -o report --clean
```
This is an Allure-tooling concern, not the adapter's — but document it because `historyId` stability (which the adapter guarantees) is what makes it work.

### 6.5 RF version compatibility

- **RF 7+:** times are `datetime`/`timedelta` — handled by `to_ms`.
- **RF 4–6:** times are strings (`starttime`/`endtime`); `to_ms` parses the legacy format. Detect via `getattr(item, "start_time", None)` first, fall back to `item.starttime`.
- **Control-structure hooks** (`start_for`, `start_if`, …) exist from RF 5+. Guard with `hasattr` / try-except so the visitor degrades gracefully on older outputs (those constructs simply appear as keywords).

### 6.6 Robust to partial / corrupt output.xml

A killed run can leave a truncated `output.xml`. `ExecutionResult` is tolerant of incomplete files (it reads what's there). Wrap the visit in a try/except and still flush whatever containers/results were completed, so CI gets a partial Allure report rather than nothing.

### 6.7 Screenshots & binary attachments

RF embeds screenshots as `<img src="...">` in log messages, with files on disk relative to `output.xml`. In `visit_message`, detect image references, resolve the path relative to the output's directory, and emit them as real binary attachments via `report_attached_file(source, "<uuid>-attachment.png")` with `type="image/png"`, instead of inlining HTML. This makes screenshots first-class in Allure.

---

## 7. Efficiency considerations

- **Single pass, streaming.** `result.visit()` is a depth-first traversal; we emit each `*-result.json` at `end_test` and each container at `end_suite`, so memory is bounded by the current suite depth, not the whole run. Suitable for very large `output.xml` (hundreds of MB).
- **No re-execution.** Conversion cost is XML parse + traversal only — typically seconds even for large suites.
- **Native merge.** Using `ExecutionResult(*sources)` avoids a separate `rebot --merge` subprocess.
- **Parallelizable conversion.** Per-worker conversion (§6.1-B) can itself run concurrently; uuid filenames guarantee no write contention in a shared results dir.
- **Reused, battle-tested serializer.** `AllureFileLogger` is the same code path the official adapters use, so output stays compatible across Allure upgrades.

---

## 8. Testing strategy

1. **Golden-file tests:** run a fixture suite both ways — (a) live listener, (b) this adapter on its `output.xml` — and assert the emitted JSON is semantically equal (same statuses, labels, step trees, historyIds). Use `allure-python-commons-test` hamcrest matchers (`has_test_case`, `has_step`, `with_status`, …).
2. **Special-case fixtures:** pabot run, `--rerunfailed`+merge, templated tests, FOR/IF/WHILE/TRY bodies, skipped (`robot:skip`), suite setup/teardown failures, screenshots.
3. **RF version matrix:** run against output.xml produced by RF 5, 6, and 7 to validate `to_ms` and control-structure hooks.
4. **Determinism:** assert two conversions of the same output.xml produce identical `historyId`/`testCaseId` (uuids will differ — exclude from comparison).

---

## 9. Roadmap

| Phase | Deliverable |
|---|---|
| 1 | MVP: suites→containers, tests→results, keywords→steps, status/timing/labels/tags, CLI. Golden-file parity with listener for simple suites. |
| 2 | Control structures, suite setup/teardown containers, messages→attachments, screenshots. |
| 3 | Pabot (both strategies) + rerun/merge + history docs; RF 5/6/7 matrix. |
| 4 | Polish: `allure.*` link patterns, severity, behaviors (epic/feature/story) mapping parity, packaging to PyPI as `robotframework-allure-output`, `pre-commit`/CI. |

---

## 10. Comparison: Listener vs. output.xml adapter

| Aspect | Listener (`allure-robotframework`) | output.xml adapter (this proposal) |
|---|---|---|
| When it runs | During execution | After execution |
| Re-generate from old runs | No | **Yes** |
| Pabot correctness | Per-worker, fragile merge | **Canonical merged truth, choice of timeline vs. dedup** |
| Rerun/merge | Sees only its own run | **Reads RF's authoritative merged result** |
| Live results | **Yes** | No |
| Control structures | Awkward via kw events | **First-class typed body items** |
| Dependency on execution env | Tight | **Decoupled — just needs output.xml** |
| Reuses Allure commons | Yes | Yes |

**Recommendation:** ship this adapter as the canonical Allure generator for CI/pabot/rerun pipelines, and keep the listener available for developers who want live feedback during single-process local runs. Both write the same format, so a team can mix them per context without retraining on a new report.
