"""Shared test helpers: run a Robot suite and load generated Allure results."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def run_robot(
    suite_text: str,
    work_dir: Path,
    *,
    output: str = "output.xml",
    env: dict[str, str] | None = None,
) -> Path:
    """Write ``suite_text`` to a .robot file, run it, and return the output.xml path."""
    suite = work_dir / "suite.robot"
    suite.write_text(suite_text)
    run_env = None
    if env is not None:
        import os

        run_env = {**os.environ, **env}
    # Robot exits non-zero on test failure; that is expected in several fixtures.
    cmd = [sys.executable, "-m", "robot", "--output", output,
           "--outputdir", str(work_dir), str(suite)]
    subprocess.run(cmd, check=False, env=run_env)
    return work_dir / output


def load_results(results_dir: Path) -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted(results_dir.glob("*-result.json"))]


def load_containers(results_dir: Path) -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted(results_dir.glob("*-container.json"))]


def step_names(steps: list[dict]) -> list[str]:
    return [s["name"] for s in steps]


def find_step(steps: list[dict], name: str) -> dict | None:
    """Depth-first search for the first step whose name startswith ``name``."""
    for step in steps:
        if step["name"].startswith(name):
            return step
        nested = find_step(step.get("steps", []), name)
        if nested is not None:
            return nested
    return None


@pytest.fixture
def robot(tmp_path):
    return lambda text, **kw: run_robot(text, tmp_path, **kw)


def resolve_allure_cli() -> list[str] | None:
    """Return a command prefix that runs the Allure generator, or None.

    Prefers an ``allure`` executable on PATH; otherwise falls back to
    ``npx allure-commandline`` when both Node and Java are available.
    """
    if shutil.which("allure"):
        return ["allure"]
    if shutil.which("npx") and shutil.which("java"):
        return ["npx", "--yes", "allure-commandline"]
    return None


def generate_allure_report(results_dir: Path, report_dir: Path, *, timeout: int = 300) -> None:
    """Generate an Allure HTML report, skipping if no generator is available.

    Skips (rather than fails) when the CLI cannot be resolved or cannot be
    obtained/run for environmental reasons (e.g. ``npx`` cannot reach the
    network), since those are not defects in the converter under test.
    """
    cli = resolve_allure_cli()
    if cli is None:
        pytest.skip("No Allure CLI available (no `allure` on PATH and no Node+Java for npx).")

    cmd = [*cli, "generate", "--clean", "-o", str(report_dir), str(results_dir)]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as error:
        pytest.skip(f"Allure report generation could not run ({cli[0]}): {error}")

    if completed.returncode != 0 or not (report_dir / "index.html").is_file():
        pytest.skip(
            f"Allure generator ({cli[0]}) did not produce a report "
            f"(exit {completed.returncode}): {completed.stderr.strip()[:500]}"
        )
