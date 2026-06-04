## ADDED Requirements

### Requirement: Convert one or more output.xml sources

The system SHALL provide a programmatic `generate(sources, results_dir, ...)` function and a console-script CLI that accept one or more `output.xml` sources (paths or globs) and write Allure result files into a target directory. When multiple sources are given, the system SHALL combine them via `robot.api.ExecutionResult(*sources)`; because the `historyId` is stable per test full name, repeated runs of the same test share a `historyId` so Allure groups them as retries with the latest attempt (by stop time) as the headline. For a single deduplicated, last-wins `output.xml`, callers MAY pre-merge sources with `rebot --merge` and pass the merged file.

#### Scenario: Single source conversion
- **WHEN** the CLI is run with one `output.xml` and a results directory
- **THEN** Allure result files for that run are written into the results directory

#### Scenario: Multiple sources are combined and grouped as retries
- **WHEN** the CLI is run with `original.xml` (a test fails) and `rerun.xml` (the same test passes)
- **THEN** both attempts are emitted as results sharing the same `historyId`
- **AND** the attempt with the latest stop time has status `passed`, so Allure shows the passing result as the headline with the earlier failure as a retry

#### Scenario: Pre-merged source yields a single result
- **WHEN** sources are merged upstream with `rebot --merge` and the merged `output.xml` is converted
- **THEN** a single result per test is written with the last-wins status

#### Scenario: Glob expansion
- **WHEN** a source argument is a glob that matches several files
- **THEN** all matching files are included as sources

### Requirement: Streaming, single-pass generation

The system SHALL convert results in a single depth-first traversal, emitting each test result at test end and each container at suite end, so peak memory is bounded by current suite depth rather than the whole run.

#### Scenario: Large output is converted without loading all results in memory
- **WHEN** a large `output.xml` is converted
- **THEN** result and container files are flushed incrementally during traversal

### Requirement: Output directory controls

The CLI SHALL default the results directory and SHALL support a `--clean` flag that removes existing files in the results directory before writing. Without `--clean`, the system SHALL append to the directory, relying on uuid filenames to avoid collisions.

#### Scenario: Clean run replaces previous results
- **WHEN** the CLI is run with `--clean` against a non-empty results directory
- **THEN** prior files are removed before the new results are written

#### Scenario: Appending across invocations
- **WHEN** the CLI is run twice without `--clean` against the same directory
- **THEN** both runs' result files coexist without overwriting each other

### Requirement: Labelling and link configuration options

The CLI SHALL accept a `--thread` option to set the thread label (e.g. a pabot worker id) and `--issue-pattern`/`--link-pattern` options forwarded to tag parsing so issue and link tags become Allure links.

#### Scenario: Thread label applied for pabot worker
- **WHEN** the CLI is run with `--thread worker-2`
- **THEN** every result produced by that invocation carries a `thread=worker-2` label

#### Scenario: Issue pattern produces links
- **WHEN** the CLI is run with an `--issue-pattern` and a test has a matching issue tag
- **THEN** the result has a corresponding issue link

### Requirement: Tolerance of partial output

The system SHALL tolerate a truncated or partially-written `output.xml`: it SHALL NOT abort with an unhandled exception, SHALL emit a warning, and SHALL flush whatever results were produced. Because `ExecutionResult` parses the source eagerly, an unparseable truncation yields no results; a source the parser can still read yields all results it recovers.

#### Scenario: Truncated output does not crash the converter
- **WHEN** the CLI converts a truncated `output.xml` from a killed run
- **THEN** the command exits without raising an unhandled exception and emits a warning
- **AND** any results the parser was able to recover are written to the output directory
