"""Suite-label and tag/link mapping, mirroring the allure-robotframework listener."""

from __future__ import annotations

from allure_commons.mapping import parse_tag
from allure_commons.model2 import Label, Link
from allure_commons.types import LabelType


def suite_labels(full_name: str) -> list[Label]:
    """Split ``Root.Mid.Leaf.Test`` into parentSuite/suite/subSuite labels.

    The final dotted segment is the test name and is dropped.
    """
    parts = full_name.split(".")[:-1]
    if not parts:
        return []
    if len(parts) == 1:
        return [Label(name=LabelType.SUITE, value=parts[0])]
    if len(parts) == 2:
        return [
            Label(name=LabelType.SUITE, value=parts[0]),
            Label(name=LabelType.SUB_SUITE, value=parts[1]),
        ]
    return [
        Label(name=LabelType.PARENT_SUITE, value=parts[0]),
        Label(name=LabelType.SUITE, value=".".join(parts[1:-1])),
        Label(name=LabelType.SUB_SUITE, value=parts[-1]),
    ]


def tag_labels_and_links(
    tags,  # noqa: ANN001 - RF tags collection
    issue_pattern: str | None = None,
    link_pattern: str | None = None,
) -> tuple[list[Label], list[Link]]:
    """Map Robot tags to Allure labels and links via ``parse_tag``."""
    labels: list[Label] = []
    links: list[Link] = []
    for tag in tags:
        parsed = parse_tag(str(tag), issue_pattern=issue_pattern, link_pattern=link_pattern)
        if isinstance(parsed, Link):
            links.append(parsed)
        else:
            labels.append(parsed)
    return labels, links
