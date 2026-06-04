# robotframework-allurevisitor

[![PyPI version](https://img.shields.io/pypi/v/robotframework-allurevisitor.svg)](https://pypi.org/project/robotframework-allurevisitor/)
[![Python versions](https://img.shields.io/pypi/pyversions/robotframework-allurevisitor.svg)](https://pypi.org/project/robotframework-allurevisitor/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/manykarim/robotframework-allurevisitor/blob/main/LICENSE)

Generate [Allure](https://allurereport.org/) input files from Robot Framework
results. It is an **offline alternative to the `allure-robotframework` listener**:
instead of hooking into a live test run, it post-processes an existing Robot
Framework `output.xml` via Robot Framework's `ResultVisitor` API and writes the
same `*-result.json` / `*-container.json` / `*-attachment.*` files using the
official `allure-python-commons` engine.

This is handy when you already have an `output.xml` (from CI, a rerun, or a
pabot run) and want an Allure report without re-running the tests.

## Installation

```bash
pip install robotframework-allurevisitor
```

This installs the `rf-allure` console script (with `allurevisitor` as an alias).
Rendering the Allure report additionally requires the
[Allure CLI](https://allurereport.org/docs/install/).

## Requirements

- Python `>=3.13`
- [uv](https://docs.astral.sh/uv/) for working on the project from source

## From source

```bash
uv sync
```

## Usage

Command line (`rf-allure`, with `allurevisitor` as an alias):

```bash
uv run rf-allure path/to/output.xml -o allure-results --clean
```

Then render the report with the Allure CLI:

```bash
allure serve allure-results
```

Programmatic:

```python
from robotframework_allurevisitor import generate

generate("output.xml", "allure-results", clean=True)
```

### CLI options

| Option | Description |
|---|---|
| `sources` | One or more `output.xml` files or globs (positional). |
| `-o, --output` | Results directory (default `allure-results`). |
| `--clean` | Remove existing files in the results directory first. |
| `--thread` | Thread label, e.g. a pabot worker id (drives the Timeline view). |
| `--issue-pattern` | Pattern turning issue tags into Allure issue links. |
| `--link-pattern` | Pattern turning link tags into Allure links. |

## What gets converted

- **Suites → containers**, with Suite Setup/Teardown recorded as the container's
  `befores`/`afters`.
- **Tests → results**, with `parentSuite`/`suite`/`subSuite` labels from the test
  full name, `framework`/`language`/`host` (and optional `thread`) labels, tags
  mapped to labels/links (`allure.*` tags, severity), and a stable
  `historyId = md5(full_name)`.
- **Keywords and control structures (FOR/IF/WHILE/TRY/…) → nested steps**, with
  keyword assignment in the step name and arguments as step parameters.
- **Status**: `PASS→passed`, `SKIP`/`NOT RUN→skipped`, `FAIL→failed`, and
  library/import/syntax/timeout errors → `broken`.
- **Timestamps** are taken from the result data (epoch ms), never wall-clock, so
  conversion is reproducible.
- **Log messages → HTML attachments** folded into the owning step; embedded
  **screenshots → binary attachments**.

## Reruns, merges, and pabot

Passing multiple sources combines them; because `historyId` is stable, repeated
runs of the same test are grouped by Allure as **retries** with the latest
attempt (by stop time) as the headline:

```bash
uv run rf-allure original.xml rerun.xml -o allure-results --clean
```

For a single, deduplicated last-wins result, pre-merge with Robot's own tooling
and convert the merged file:

```bash
rebot --merge original.xml rerun.xml --output merged.xml
uv run rf-allure merged.xml -o allure-results --clean
```

For **pabot**, either convert the single merged `output.xml`, or convert each
worker's file with a distinct `--thread` — but never both into the same results
directory (identical `historyId` would inflate counts).

Allure's trend/history view additionally relies on copying the previous report's
`history/` directory into `allure-results` before `allure generate`; that is an
Allure-tooling step, enabled by the stable `historyId` this tool produces.

## Development

```bash
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # format
```

### End-to-end test

`tests/test_e2e_report.py` runs the whole pipeline — Robot Framework → the
packaged `rf-allure` CLI → a real Allure HTML report — and asserts the report's
`widgets/summary.json` statistics and `data/test-cases/` match the run. It is
tagged with the `e2e` marker:

```bash
uv run pytest -m e2e          # only the end-to-end test
uv run pytest -m "not e2e"    # skip it (hermetic fast lane)
```

Generating the report needs an Allure CLI. The test resolves one automatically:
it uses `allure` if on `PATH`, otherwise falls back to `npx allure-commandline`
(which needs Node and Java). If neither is available it **skips** rather than
failing. To install a generator:

```bash
# Option A: the standalone Allure CLI (https://allurereport.org/docs/install/)
# Option B: via npm (Java required)
npm install -g allure-commandline
```

The `npx allure-commandline` fallback downloads the package on first use.

See [AGENTS.md](AGENTS.md) for architecture and contribution notes.
