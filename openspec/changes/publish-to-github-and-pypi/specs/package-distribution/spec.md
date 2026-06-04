## ADDED Requirements

### Requirement: Apache-2.0 licensing

The project SHALL include the full Apache-2.0 license text in a top-level `LICENSE` file and SHALL declare it in package metadata using the SPDX expression `Apache-2.0` with the `LICENSE` file referenced via `license-files`, so the license is carried into the built distributions.

#### Scenario: License file present and declared
- **WHEN** the repository and a built distribution are inspected
- **THEN** a top-level `LICENSE` file contains the Apache-2.0 text
- **AND** the package metadata declares the `Apache-2.0` license and includes the license file

### Requirement: Complete distribution metadata

The package metadata in `pyproject.toml` SHALL be release-ready: a non-placeholder description, authors, keywords, Trove classifiers (including the Python version, Robot Framework framework, and testing/reporting topics), `requires-python`, and `project.urls` for the homepage/repository and issue tracker. The distribution name SHALL remain `robotframework-allurevisitor`.

#### Scenario: Metadata is no longer the scaffold default
- **WHEN** `pyproject.toml` is inspected
- **THEN** the description is project-specific (not "Add your description here")
- **AND** authors, keywords, classifiers, and project URLs are populated

### Requirement: Build produces an installable distribution

`uv build` SHALL produce both an sdist and a wheel without errors, and installing the wheel into a clean environment SHALL expose the `rf-allure` (and `allurevisitor`) console script and allow `import robotframework_allurevisitor` to succeed.

#### Scenario: Wheel and sdist build
- **WHEN** `uv build` is run
- **THEN** a `.whl` and a `.tar.gz` are produced under `dist/`

#### Scenario: Installed distribution exposes the CLI
- **WHEN** the built wheel is installed into a clean environment
- **THEN** the `rf-allure` console script is available and runs
- **AND** `import robotframework_allurevisitor` succeeds

### Requirement: Publish-clean repository contents

The repository SHALL commit the source, tests, OpenSpec specs, lockfile, and documentation, and SHALL exclude generated and local-only artifacts (`dist/`, `reports/`, `allure-results/`, `.venv/`, and local agent directories) via `.gitignore`.

#### Scenario: Generated artifacts are ignored
- **WHEN** the working tree is checked after a build and a report generation
- **THEN** `dist/`, `reports/`, and `allure-results/` are not tracked by git

#### Scenario: Essential files are tracked
- **WHEN** the committed file set is inspected
- **THEN** it includes `src/`, `tests/`, `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE`, and the `openspec/` specs

### Requirement: Public GitHub hosting on main

The project SHALL be hosted in a public GitHub repository `manykarim/robotframework-allurevisitor` whose default branch is `main`, with all needed files pushed.

#### Scenario: Repository exists and is public
- **WHEN** the GitHub repository is queried
- **THEN** `manykarim/robotframework-allurevisitor` exists, is public, and its default branch is `main`

#### Scenario: Files are pushed
- **WHEN** the remote `main` branch is inspected
- **THEN** it contains the committed source, tests, docs, license, and specs

### Requirement: Published to PyPI

The distribution SHALL be published to PyPI via `uv publish` using an API token supplied at run time (e.g. `UV_PUBLISH_TOKEN`), with the token never committed to the repository. After publication the package SHALL be installable from PyPI.

#### Scenario: Package is published without storing credentials
- **WHEN** `uv publish` uploads the built artifacts
- **THEN** the upload uses a token provided via the environment, not a value stored in the repo

#### Scenario: Installable from PyPI
- **WHEN** `pip install robotframework-allurevisitor` is run after publication
- **THEN** the package installs and the `rf-allure` console script is available

### Requirement: Release documentation

The documentation SHALL present the package for public consumption: `README.md` SHALL include install-from-PyPI instructions and render correctly as the PyPI long description, and a `CHANGELOG.md` SHALL record the `0.1.0` release.

#### Scenario: README is PyPI-ready
- **WHEN** `README.md` is inspected
- **THEN** it documents `pip install robotframework-allurevisitor` and is referenced as the package `readme`

#### Scenario: Changelog records the release
- **WHEN** `CHANGELOG.md` is inspected
- **THEN** it contains a `0.1.0` entry describing the initial release
