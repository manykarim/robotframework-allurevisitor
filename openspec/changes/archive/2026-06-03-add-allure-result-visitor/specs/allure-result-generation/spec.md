## ADDED Requirements

### Requirement: Reuse the official Allure model and serializer

The system SHALL build Allure result objects using `allure-python-commons` model classes (`TestResult`, `TestResultContainer`, `TestStepResult`, `TestBeforeResult`, `TestAfterResult`, `Label`, `Link`, `Parameter`, `Attachment`, `StatusDetails`, `Status`) and SHALL write them to disk via the official `allure_commons.logger.AllureFileLogger`. The system SHALL NOT reimplement Allure JSON serialization.

#### Scenario: Output is byte-compatible with the Allure ecosystem
- **WHEN** the generator writes results for a run
- **THEN** the results directory contains `<uuid>-result.json`, `<uuid>-container.json`, and `<uuid>-attachment.*` files produced by `AllureFileLogger`
- **AND** the files are consumable by `allure generate` without modification

### Requirement: Suites map to containers with setup and teardown

The system SHALL map each Robot Framework suite to a `TestResultContainer`, nesting child suites and tests via the container `children` list, and SHALL record suite setup as a `before` and suite teardown as an `after` on the owning container.

#### Scenario: Nested suites form a container tree
- **WHEN** a suite contains a child suite and tests
- **THEN** the parent container's `children` includes the child container's uuid and each test's uuid

#### Scenario: Suite setup and teardown are captured
- **WHEN** a suite defines a Suite Setup and Suite Teardown
- **THEN** the suite's container records the setup keyword under `befores` and the teardown keyword under `afters`

### Requirement: Tests map to results

The system SHALL map each Robot Framework test case to a `TestResult` with `name`, `fullName` (from `full_name`), `description` (from `doc`), and SHALL report the result when the test ends.

#### Scenario: Each test produces one result file
- **WHEN** a suite runs three tests
- **THEN** three `*-result.json` files are written, one per test, each with the test name and full name

### Requirement: Keywords and control structures map to nested steps

The system SHALL map keywords to nested `TestStepResult` items and SHALL represent control structures (FOR, FOR iteration, IF, IF branch, WHILE, TRY, TRY branch, GROUP, VAR) as labelled steps, preserving Robot's nesting via a traversal stack. Keyword assignment SHALL be reflected in the step name and keyword arguments SHALL be recorded as step parameters.

#### Scenario: Nested keywords preserve hierarchy
- **WHEN** a test calls a keyword that calls another keyword
- **THEN** the outer step contains the inner step in its `steps` list

#### Scenario: Control structures are represented as steps
- **WHEN** a test body contains a FOR loop with iterations and an IF block
- **THEN** the FOR, its iterations, the IF, and its branches appear as labelled steps in the step tree

#### Scenario: Assignment and arguments are surfaced
- **WHEN** a keyword `${x} = Some Keyword    arg0    arg1` runs
- **THEN** the step name includes the assignment and the arguments are recorded as step parameters

### Requirement: Timestamps are derived from result data

The system SHALL derive every `start` and `stop` value as epoch milliseconds from the Robot Framework result's own `start_time`/`end_time` and SHALL NOT use wall-clock time at conversion. It SHALL support Robot Framework 7+ `datetime` values and legacy string timestamps (`YYYYMMDD HH:MM:SS.fff`).

#### Scenario: RF 7 datetime timestamps are converted
- **WHEN** a test's `start_time` is a `datetime`
- **THEN** the result `start` equals `int(round(start_time.timestamp() * 1000))`

#### Scenario: Two conversions of the same output.xml yield equal timings
- **WHEN** the same `output.xml` is converted twice
- **THEN** the `start`/`stop` values are identical across both conversions

### Requirement: Status is mapped with details

The system SHALL map Robot statuses to Allure statuses: PASS → passed, SKIP and NOT_RUN → skipped, and FAIL → failed for assertion failures or broken for library/syntax/import/timeout errors. When a failure or skip message exists, the system SHALL populate `StatusDetails.message`.

#### Scenario: Passing test
- **WHEN** a test status is PASS
- **THEN** the result status is `passed` and `statusDetails` is empty

#### Scenario: Assertion failure
- **WHEN** a test fails with an assertion message
- **THEN** the result status is `failed` and `statusDetails.message` contains the failure message

#### Scenario: Library or syntax error
- **WHEN** a test fails because a keyword could not be found or imported
- **THEN** the result status is `broken`

#### Scenario: Skipped test
- **WHEN** a test is skipped
- **THEN** the result status is `skipped`

### Requirement: Labels, tags, links, and stable identity

The system SHALL derive suite labels from the test `full_name` (`parentSuite`/`suite`/`subSuite`, dropping the test name), add `framework`, `language`, and `host` labels, and add a `thread` label when one is supplied. It SHALL map Robot tags to Allure labels and links using `allure_commons.mapping.parse_tag` (including severity and `allure.*` tags). It SHALL set `testCaseId` and `historyId` to `md5(full_name [+ sorted parameter values])` so identity is stable across reruns.

#### Scenario: Suite hierarchy becomes suite labels
- **WHEN** a test full name is `Root.Mid.Leaf.My Test`
- **THEN** the result has `parentSuite=Root`, `suite=Mid`, and `subSuite=Leaf` labels

#### Scenario: Tags become labels and links
- **WHEN** a test has tags `severity:critical` and `allure.issue:ABC-1`
- **THEN** a severity label and an issue link are present on the result

#### Scenario: historyId is stable across runs
- **WHEN** the same test (same full name and parameters) is converted from two different runs
- **THEN** both results have the same `historyId`

### Requirement: Messages and screenshots become attachments

The system SHALL fold Robot log messages into the currently-owning step (or the test) as HTML attachments preserving the message level, and SHALL resolve embedded screenshot references to first-class binary attachments written via `report_attached_file` with the correct MIME type and a path resolved relative to the `output.xml` directory.

#### Scenario: Log message folded into the owning step
- **WHEN** a keyword logs an INFO message
- **THEN** the keyword's step gains an HTML attachment whose content includes the level and message text

#### Scenario: Screenshot becomes a binary attachment
- **WHEN** a log message embeds an image reference to a file on disk
- **THEN** an image attachment is emitted via `report_attached_file` with an image MIME type
