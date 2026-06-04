# e2e-report-verification Specification

## Purpose

Define an automated end-to-end test that exercises the full Robot Framework -> `rf-allure` -> Allure report pipeline, verifies the generated report reflects the run, resolves an Allure CLI portably (with a graceful skip when unavailable), and is selectable via a registered `e2e` pytest marker.

## Requirements

### Requirement: End-to-end pipeline test

The project SHALL include an automated end-to-end test that, in one run, executes a Robot Framework suite to produce an `output.xml`, converts it with the installed `rf-allure` console script (invoked as a subprocess), generates an Allure HTML report from the produced results, and asserts the report exists and is well-formed.

#### Scenario: Full pipeline produces a report
- **WHEN** the end-to-end test runs with an available Allure generator
- **THEN** a Robot `output.xml` is produced, converted to an `allure-results` directory by `rf-allure`, and an Allure report directory is generated
- **AND** the report directory contains an `index.html` file

#### Scenario: Conversion is exercised through the packaged CLI
- **WHEN** the end-to-end test performs the conversion step
- **THEN** it invokes the `rf-allure` console-script entry point as a subprocess (not the in-process `generate` function), so the package's entry point is exercised

### Requirement: Report reflects the run

The end-to-end test SHALL use a representative suite covering passed, failed, skipped, and broken tests, and SHALL assert that the generated report's statistics match the run and that one report test case exists per executed test.

#### Scenario: Summary statistics match status counts
- **WHEN** the report is generated from a suite with known passed/failed/skipped/broken counts
- **THEN** the report's `widgets/summary.json` statistic counts equal those known counts

#### Scenario: Every test appears in the report
- **WHEN** the report is generated
- **THEN** the report's `data/test-cases/` directory contains one entry per executed test

### Requirement: Portable Allure-CLI resolution with graceful skip

The end-to-end test SHALL resolve an Allure report generator by preferring an `allure` executable on `PATH` and otherwise falling back to `npx allure-commandline` when Node and Java are available. When no generator can be resolved, the test SHALL be skipped (reported as skipped, not failed), so the overall suite stays green on machines without an Allure CLI.

#### Scenario: Allure on PATH is used
- **WHEN** an `allure` executable is on `PATH`
- **THEN** the test uses it to generate the report

#### Scenario: Fallback to npx allure-commandline
- **WHEN** no `allure` executable is on `PATH` but Node and Java are available
- **THEN** the test uses `npx allure-commandline` to generate the report

#### Scenario: Graceful skip when unavailable
- **WHEN** neither an `allure` executable nor the Node+Java fallback is available
- **THEN** the end-to-end test is skipped rather than failing

### Requirement: Selectable e2e marker

The end-to-end test SHALL be tagged with a registered `e2e` pytest marker so it can be included or excluded via `-m e2e` / `-m "not e2e"`, while still running by default and self-skipping when its prerequisites are unmet.

#### Scenario: Deselecting e2e tests
- **WHEN** pytest is run with `-m "not e2e"`
- **THEN** the end-to-end test is not collected and no marker-related warning is emitted
