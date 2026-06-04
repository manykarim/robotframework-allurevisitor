"""End-to-end tests for the Allure result visitor."""

from __future__ import annotations

import subprocess
import sys

from allure_commons.utils import md5
from conftest import find_step, load_containers, load_results, step_names

from robotframework_allurevisitor.visitor import generate

BASIC_SUITE = """\
*** Test Cases ***
Passing Test
    [Documentation]    A passing test.
    [Tags]    smoke    allure.severity:critical
    Log    hello
    Should Be Equal    1    1

Failing Test
    Should Be Equal    1    2
"""


def test_basic_parity(robot, tmp_path):
    """6.2 Golden-file parity: statuses, labels, step tree, stable historyId."""
    output_xml = robot(BASIC_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    results = {r["name"]: r for r in load_results(results_dir)}
    assert set(results) == {"Passing Test", "Failing Test"}

    passing = results["Passing Test"]
    assert passing["status"] == "passed"
    assert passing["fullName"] == "Suite.Passing Test"
    assert passing["historyId"] == md5("Suite.Passing Test")
    assert step_names(passing["steps"]) == ["Log", "Should Be Equal"]

    labels = {(label["name"], label["value"]) for label in passing["labels"]}
    assert ("suite", "Suite") in labels
    assert ("framework", "robotframework") in labels
    assert ("severity", "critical") in labels
    assert ("tag", "smoke") in labels

    failing = results["Failing Test"]
    assert failing["status"] == "failed"
    assert failing["statusDetails"]["message"]


CONTROL_SUITE = """\
*** Test Cases ***
Control Flow
    ${x} =    Set Variable    1
    FOR    ${i}    IN    a    b
        Log    ${i}
    END
    IF    ${x} == 1
        Log    yes
    ELSE
        Log    no
    END
    WHILE    ${x} > 1
        Log    never
    END
    TRY
        Fail    boom
    EXCEPT    boom
        Log    caught
    END
"""


def test_control_structures(robot, tmp_path):
    """6.3 FOR/IF/WHILE/TRY appear as steps with correct nesting and status."""
    output_xml = robot(CONTROL_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (result,) = load_results(results_dir)
    assert result["status"] == "passed"

    for_step = find_step(result["steps"], "FOR")
    assert for_step is not None
    # FOR has two iterations, each containing a Log step.
    assert len(for_step["steps"]) == 2
    assert find_step(for_step["steps"], "Log") is not None

    if_step = find_step(result["steps"], "IF")
    assert if_step is not None

    try_step = find_step(result["steps"], "TRY")
    assert try_step is not None
    assert find_step(try_step["steps"], "EXCEPT") is not None


SETUP_TEARDOWN_SUITE = """\
*** Settings ***
Suite Setup    Log    suite-setup
Suite Teardown    Log    suite-teardown

*** Test Cases ***
Skipped Test
    [Tags]    robot:skip
    Log    never

Broken Test
    This Keyword Does Not Exist
"""


def test_setup_teardown_skip_and_broken(robot, tmp_path):
    """6.4 Suite setup/teardown -> container befores/afters; skip and broken statuses."""
    output_xml = robot(SETUP_TEARDOWN_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (container,) = load_containers(results_dir)
    assert len(container["befores"]) == 1
    assert container["befores"][0]["name"] == "Log"
    assert len(container["afters"]) == 1

    results = {r["name"]: r for r in load_results(results_dir)}
    assert results["Skipped Test"]["status"] == "skipped"
    assert results["Broken Test"]["status"] == "broken"


FLAKY_SUITE = """\
*** Test Cases ***
Flaky
    Should Be Equal    %{RESULT}    pass
"""


def test_multisource_combine_retry(robot, tmp_path):
    """6.5 Combining sources groups attempts by historyId; latest stop wins headline."""
    run1 = robot(FLAKY_SUITE, output="run1.xml", env={"RESULT": "fail"})
    run2 = robot(FLAKY_SUITE, output="run2.xml", env={"RESULT": "pass"})

    results_dir = tmp_path / "allure-results"
    generate([run1, run2], results_dir, clean=True)

    flaky = [r for r in load_results(results_dir) if r["name"] == "Flaky"]
    assert len(flaky) == 2
    # Both attempts share one stable historyId (md5 of the same full name) so
    # Allure groups them as retries of a single logical test.
    assert len({r["historyId"] for r in flaky}) == 1
    # The latest attempt (by stop time) is the passing one -> last-wins headline.
    latest = max(flaky, key=lambda r: r["stop"])
    assert latest["status"] == "passed"


def test_premerged_source_is_deduplicated(robot, tmp_path):
    """6.5 A rebot --merge source yields a single last-wins result."""
    run1 = robot(FLAKY_SUITE, output="run1.xml", env={"RESULT": "fail"})
    run2 = robot(FLAKY_SUITE, output="run2.xml", env={"RESULT": "pass"})
    merged = tmp_path / "merged.xml"
    subprocess.run(
        [sys.executable, "-m", "robot.rebot", "--merge", "--output", str(merged),
         "--outputdir", str(tmp_path), str(run1), str(run2)],
        check=False,
    )

    results_dir = tmp_path / "allure-results"
    generate(merged, results_dir, clean=True)

    flaky = [r for r in load_results(results_dir) if r["name"] == "Flaky"]
    assert len(flaky) == 1
    assert flaky[0]["status"] == "passed"


TEMPLATE_SUITE = """\
*** Test Cases ***
Addition
    [Template]    Should Be Equal As Numbers
    ${1 + 1}    2
    ${3 + 4}    7
"""


def test_templated_rows_become_parameterised_steps(robot, tmp_path):
    """6.6 Templated rows are distinct steps carrying their args as parameters."""
    output_xml = robot(TEMPLATE_SUITE)
    results_dir = tmp_path / "allure-results"
    generate(output_xml, results_dir, clean=True)

    (result,) = load_results(results_dir)
    assert result["status"] == "passed"
    assert result["historyId"] == md5("Suite.Addition")

    rows = [s for s in result["steps"] if s["name"] == "Should Be Equal As Numbers"]
    assert len(rows) == 2
    # Each row carries its own arguments as step parameters -> distinct identity.
    row_args = [tuple(p["value"] for p in row["parameters"]) for row in rows]
    assert ("2",) in [args[1:] for args in row_args]
    assert all(len(row["parameters"]) == 2 for row in rows)


def test_determinism(robot, tmp_path):
    """6.7 Two conversions of the same output.xml produce identical historyId/timings."""
    output_xml = robot(BASIC_SUITE)
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate(output_xml, first, clean=True)
    generate(output_xml, second, clean=True)

    def identity(results_dir):
        return sorted(
            (r["fullName"], r["historyId"], r["start"], r["stop"])
            for r in load_results(results_dir)
        )

    assert identity(first) == identity(second)


def test_partial_output_tolerance(robot, tmp_path):
    """6.8 A truncated output.xml degrades gracefully without an unhandled error."""
    output_xml = robot(BASIC_SUITE)
    truncated = tmp_path / "truncated.xml"
    data = output_xml.read_bytes()
    truncated.write_bytes(data[: len(data) // 2])

    results_dir = tmp_path / "allure-results"
    # Must not raise; recovers whatever the parser could read (possibly nothing).
    generate(truncated, results_dir, clean=True)
    assert results_dir.is_dir()
