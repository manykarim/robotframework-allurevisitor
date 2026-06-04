# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-04

Initial release.

### Added
- `AllureResultVisitor`, a stack-based Robot Framework `ResultVisitor` that
  converts an `output.xml` into Allure result files using the official
  `allure-python-commons` model and file logger.
- Mapping of suites to containers (with suite setup/teardown as
  `befores`/`afters`), tests to results, and keywords plus control structures
  (FOR/IF/WHILE/TRY/GROUP/VAR) to nested steps.
- Status mapping (`passed`/`failed`/`skipped`/`broken`), data-derived
  timestamps, `parentSuite`/`suite`/`subSuite` and tag/link labels, stable
  `historyId`, and message/screenshot attachments.
- `generate()` API and the `rf-allure` (alias `allurevisitor`) console script,
  supporting multiple sources, `--clean`, `--thread`, and issue/link patterns.
- Unit tests plus an end-to-end test that runs the full
  Robot → `rf-allure` → Allure report pipeline.

[0.1.0]: https://github.com/manykarim/robotframework-allurevisitor/releases/tag/v0.1.0
