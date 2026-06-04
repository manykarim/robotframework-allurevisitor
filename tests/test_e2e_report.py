"""End-to-end pipeline test: Robot -> rf-allure (CLI) -> Allure report.

Exercises the full chain a user runs and asserts the generated report's
machine-readable data reflects the run. Skips cleanly when no Allure generator
is available.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import generate_allure_report

# Representative suite driving every status bucket plus setup/teardown, a FOR/IF
# block, and a logged message. Known counts: 1 passed, 1 failed, 1 skipped,
# 1 broken (4 total).
E2E_SUITE = """\
*** Settings ***
Suite Setup    Log    starting suite
Suite Teardown    Log    finishing suite

*** Test Cases ***
Passing Test
    [Tags]    allure.severity:critical    feature:reporting
    Log    a passing test
    FOR    ${i}    IN    1    2
        Log    iteration ${i}
    END
    IF    1 == 1
        Log    branch taken
    END

Failing Test
    Should Be Equal    1    2

Skipped Test
    [Tags]    robot:skip
    Log    never runs

Broken Test
    This Keyword Does Not Exist
"""

EXPECTED_COUNTS = {"passed": 1, "failed": 1, "skipped": 1, "broken": 1, "total": 4}


def _resolve_rf_allure() -> str | None:
    """Locate the installed ``rf-allure`` console script."""
    found = shutil.which("rf-allure")
    if found:
        return found
    candidate = Path(sys.executable).parent / "rf-allure"
    return str(candidate) if candidate.exists() else None


@pytest.mark.e2e
def test_full_pipeline_to_allure_report(robot, tmp_path):
    # 1. Run Robot Framework -> output.xml
    output_xml = robot(E2E_SUITE)

    # 2. Convert via the packaged rf-allure console script (subprocess).
    rf_allure = _resolve_rf_allure()
    if rf_allure is None:
        pytest.skip("rf-allure console script is not installed on PATH.")
    results_dir = tmp_path / "allure-results"
    convert = subprocess.run(
        [rf_allure, str(output_xml), "-o", str(results_dir), "--clean"],
        capture_output=True,
        text=True,
    )
    assert convert.returncode == 0, convert.stderr
    assert list(results_dir.glob("*-result.json")), "conversion produced no results"

    # 3. Generate a real Allure report (skips if no generator is available).
    report_dir = tmp_path / "allure-report"
    generate_allure_report(results_dir, report_dir)

    # 4. The report exists and is well-formed.
    assert (report_dir / "index.html").is_file()

    # 5. Summary statistics match the known status counts.
    summary_path = report_dir / "widgets" / "summary.json"
    if not summary_path.is_file():
        pytest.skip(f"Unrecognized Allure report layout: {summary_path} missing.")
    statistic = json.loads(summary_path.read_text()).get("statistic")
    if statistic is None:
        pytest.skip("Unrecognized Allure summary.json schema: no 'statistic' key.")
    for status, expected in EXPECTED_COUNTS.items():
        assert statistic.get(status) == expected, (
            f"{status}: expected {expected}, got {statistic.get(status)} ({statistic})"
        )

    # 6. One report test case per executed test.
    test_cases = list((report_dir / "data" / "test-cases").glob("*.json"))
    assert len(test_cases) == EXPECTED_COUNTS["total"]
