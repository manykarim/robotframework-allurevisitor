"""Command line entry point for the Allure result visitor."""

from __future__ import annotations

import argparse
import glob
import sys
from collections.abc import Sequence

from robotframework_allurevisitor.visitor import generate


def _expand(sources: list[str]) -> list[str]:
    """Expand glob patterns, keeping literal paths that match nothing."""
    expanded: list[str] = []
    for source in sources:
        matches = glob.glob(source)
        expanded.extend(matches or [source])
    return expanded


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rf-allure",
        description="Generate Allure input files from Robot Framework output.xml file(s).",
    )
    parser.add_argument("sources", nargs="+", help="output.xml file(s) or glob(s)")
    parser.add_argument(
        "-o",
        "--output",
        default="allure-results",
        help="Directory to write Allure result files into (default: allure-results).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing files in the output directory before writing.",
    )
    parser.add_argument(
        "--thread",
        default=None,
        help="Thread label for the results (e.g. a pabot worker id).",
    )
    parser.add_argument("--issue-pattern", default=None, help="Pattern for issue links.")
    parser.add_argument("--link-pattern", default=None, help="Pattern for generic links.")
    args = parser.parse_args(argv)

    generate(
        _expand(args.sources),
        args.output,
        clean=args.clean,
        thread=args.thread,
        issue_pattern=args.issue_pattern,
        link_pattern=args.link_pattern,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
