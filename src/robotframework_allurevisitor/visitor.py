"""Stack-based Robot Framework ``ResultVisitor`` that emits Allure files.

The visitor walks ``robot.api.ExecutionResult`` depth-first and reports each
container at ``end_suite`` and each test result at ``end_test``, so peak memory
is bounded by the current suite/keyword depth rather than the whole run.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from allure_commons.logger import AllureFileLogger
from allure_commons.model2 import (
    Attachment,
    Label,
    Parameter,
    TestAfterResult,
    TestBeforeResult,
    TestResult,
    TestResultContainer,
    TestStepResult,
)
from allure_commons.types import LabelType
from allure_commons.utils import host_tag, platform_label, uuid4
from robot.api import ExecutionResult, ResultVisitor

from robotframework_allurevisitor._convert import history_id, status_of, to_ms
from robotframework_allurevisitor._labels import suite_labels, tag_labels_and_links

# Matches an <img src="..."> reference inside a Robot log message.
_IMG_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)

_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


class AllureResultVisitor(ResultVisitor):
    """Convert a Robot Framework result tree into Allure result files."""

    def __init__(
        self,
        logger: AllureFileLogger,
        *,
        source_dir: str | Path | None = None,
        host: str | None = None,
        thread: str | None = None,
        issue_pattern: str | None = None,
        link_pattern: str | None = None,
    ) -> None:
        self._logger = logger
        self._source_dir = Path(source_dir) if source_dir else None
        self._host = host or host_tag()
        self._thread = thread
        self._platform = platform_label()
        self._issue_pattern = issue_pattern
        self._link_pattern = link_pattern
        self._containers: list[TestResultContainer] = []
        self._steps: list = []  # stack of ExecutableItem (test / keyword / control)
        self._test: TestResult | None = None

    # ----------------------------------------------------------------- suites
    def start_suite(self, suite) -> None:  # noqa: ANN001
        self._containers.append(
            TestResultContainer(
                uuid=uuid4(),
                name=suite.name,
                start=to_ms(suite.start_time),
                stop=to_ms(suite.end_time),
            )
        )

    def end_suite(self, suite) -> None:  # noqa: ANN001
        container = self._containers.pop()
        if self._containers:
            self._containers[-1].children.append(container.uuid)
        self._logger.report_container(container)

    # ------------------------------------------------------------------ tests
    def start_test(self, test) -> None:  # noqa: ANN001
        full_name = getattr(test, "full_name", None) or test.longname
        labels = suite_labels(full_name)
        tag_labels, links = tag_labels_and_links(
            test.tags, self._issue_pattern, self._link_pattern
        )
        labels += tag_labels
        labels += [
            Label(name=LabelType.FRAMEWORK, value="robotframework"),
            Label(name=LabelType.LANGUAGE, value=self._platform),
            Label(name=LabelType.HOST, value=self._host),
        ]
        if self._thread:
            labels.append(Label(name=LabelType.THREAD, value=self._thread))

        status, details = status_of(test)
        result = TestResult(
            uuid=uuid4(),
            name=test.name,
            fullName=full_name,
            testCaseId=history_id(full_name),
            historyId=history_id(full_name),
            status=status,
            statusDetails=details,
            description=test.doc or None,
            start=to_ms(test.start_time),
            stop=to_ms(test.end_time),
            labels=labels,
            links=links,
            titlePath=full_name.split(".")[:-1],
        )
        self._test = result
        self._steps.append(result)
        if self._containers:
            self._containers[-1].children.append(result.uuid)

    def end_test(self, test) -> None:  # noqa: ANN001
        self._steps.pop()
        self._logger.report_result(self._test)
        self._test = None

    # -------------------------------------------------------------- keywords
    def start_keyword(self, kw) -> None:  # noqa: ANN001
        # Suite setup/teardown arrive as keywords while no test is active; they
        # belong on the container as befores/afters rather than as steps.
        if getattr(kw, "type", None) in ("SETUP", "TEARDOWN") and self._test is None:
            factory = TestBeforeResult if kw.type == "SETUP" else TestAfterResult
            status, details = status_of(kw)
            item = factory(
                name=kw.name,
                status=status,
                statusDetails=details,
                start=to_ms(kw.start_time),
                stop=to_ms(getattr(kw, "end_time", None)),
            )
            self._steps.append(item)
            return

        status, details = status_of(kw)
        step = TestStepResult(
            name=self._keyword_name(kw),
            status=status,
            statusDetails=details,
            start=to_ms(kw.start_time),
            stop=to_ms(getattr(kw, "end_time", None)),
        )
        for index, arg in enumerate(getattr(kw, "args", ()) or ()):
            step.parameters.append(Parameter(name=f"arg{index}", value=str(arg)))
        self._attach(step)
        self._steps.append(step)

    def end_keyword(self, kw) -> None:  # noqa: ANN001
        item = self._steps.pop()
        if isinstance(item, TestBeforeResult):
            self._containers[-1].befores.append(item)
        elif isinstance(item, TestAfterResult):
            self._containers[-1].afters.append(item)

    # ------------------------------------------------------- control structures
    def start_for(self, item) -> None:  # noqa: ANN001
        flavor = getattr(item, "flavor", "IN")
        assign = ", ".join(getattr(item, "assign", ()) or ())
        self._push_control(item, f"FOR {assign} {flavor}".strip())

    def end_for(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_for_iteration(self, item) -> None:  # noqa: ANN001
        assign = getattr(item, "assign", None) or {}
        label = ", ".join(f"{k}={v}" for k, v in assign.items()) or "iteration"
        self._push_control(item, label)

    def end_for_iteration(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_if(self, item) -> None:  # noqa: ANN001
        self._push_control(item, "IF")

    def end_if(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_if_branch(self, item) -> None:  # noqa: ANN001
        condition = getattr(item, "condition", None) or ""
        self._push_control(item, f"{item.type} {condition}".strip())

    def end_if_branch(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_while(self, item) -> None:  # noqa: ANN001
        condition = getattr(item, "condition", None) or ""
        self._push_control(item, f"WHILE {condition}".strip())

    def end_while(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_while_iteration(self, item) -> None:  # noqa: ANN001
        self._push_control(item, "iteration")

    def end_while_iteration(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_try(self, item) -> None:  # noqa: ANN001
        self._push_control(item, "TRY")

    def end_try(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_try_branch(self, item) -> None:  # noqa: ANN001
        patterns = " ".join(getattr(item, "patterns", ()) or ())
        self._push_control(item, f"{item.type} {patterns}".strip())

    def end_try_branch(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_group(self, item) -> None:  # noqa: ANN001
        self._push_control(item, f"GROUP {getattr(item, 'name', '') or ''}".strip())

    def end_group(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def start_var(self, item) -> None:  # noqa: ANN001
        self._push_control(item, f"VAR {getattr(item, 'name', '') or ''}".strip())

    def end_var(self, item) -> None:  # noqa: ANN001
        self._pop_control()

    def _leaf_control(self, item, label) -> None:  # noqa: ANN001
        # RETURN / BREAK / CONTINUE / ERROR have no nested body; emit and unwind.
        self._push_control(item, label)
        self._pop_control()

    def start_return(self, item) -> None:  # noqa: ANN001
        self._leaf_control(item, "RETURN")

    def start_break(self, item) -> None:  # noqa: ANN001
        self._leaf_control(item, "BREAK")

    def start_continue(self, item) -> None:  # noqa: ANN001
        self._leaf_control(item, "CONTINUE")

    def start_error(self, item) -> None:  # noqa: ANN001
        self._leaf_control(item, "ERROR")

    # ------------------------------------------------------------- messages
    def visit_message(self, message) -> None:  # noqa: ANN001
        target = self._steps[-1] if self._steps else self._test
        if target is None:
            return
        if message.html and self._attach_images(target, message.message):
            return
        body = f"<p><b>[{message.level}]</b>&nbsp;{message.message}</p>"
        file_name = f"{uuid4()}-attachment.html"
        self._logger.report_attached_data(body, file_name)
        target.attachments.append(
            Attachment(name=f"Log [{message.level}]", source=file_name, type="text/html")
        )

    def _attach_images(self, target, html: str) -> bool:  # noqa: ANN001
        attached = False
        for src in _IMG_RE.findall(html):
            resolved = self._resolve(src)
            if resolved is None:
                continue
            mime = _IMAGE_MIME.get(resolved.suffix.lower(), "application/octet-stream")
            file_name = f"{uuid4()}-attachment{resolved.suffix.lower()}"
            self._logger.report_attached_file(str(resolved), file_name)
            target.attachments.append(
                Attachment(name=resolved.name, source=file_name, type=mime)
            )
            attached = True
        return attached

    def _resolve(self, src: str) -> Path | None:
        path = Path(src)
        if not path.is_absolute() and self._source_dir is not None:
            path = self._source_dir / path
        return path if path.is_file() else None

    # ------------------------------------------------------------- internals
    def _push_control(self, item, name: str) -> None:  # noqa: ANN001
        status, details = status_of(item)
        step = TestStepResult(
            name=name,
            status=status,
            statusDetails=details,
            start=to_ms(getattr(item, "start_time", None)),
            stop=to_ms(getattr(item, "end_time", None)),
        )
        self._attach(step)
        self._steps.append(step)

    def _pop_control(self) -> None:
        self._steps.pop()

    def _attach(self, step: TestStepResult) -> None:
        parent = self._steps[-1] if self._steps else self._test
        if parent is not None:
            parent.steps.append(step)

    def _keyword_name(self, kw) -> str:  # noqa: ANN001
        name = kw.name
        assign = getattr(kw, "assign", None)
        if assign:
            name = f"{', '.join(assign)} = {name}"
        return name


def generate(
    sources,  # noqa: ANN001 - str | Path | sequence thereof
    results_dir: str | Path,
    *,
    clean: bool = False,
    thread: str | None = None,
    issue_pattern: str | None = None,
    link_pattern: str | None = None,
) -> None:
    """Convert one or more Robot ``output.xml`` sources into Allure results.

    Multiple sources are merged using Robot Framework's native last-wins
    semantics. A truncated ``output.xml`` is tolerated: whatever was completed
    is still flushed.
    """
    if isinstance(sources, (str, Path)):
        sources = [sources]
    sources = [str(s) for s in sources]
    source_dir = Path(sources[0]).resolve().parent if sources else None

    logger = AllureFileLogger(str(results_dir), clean=clean)
    visitor = AllureResultVisitor(
        logger,
        source_dir=source_dir,
        thread=thread,
        issue_pattern=issue_pattern,
        link_pattern=link_pattern,
    )
    try:
        result = ExecutionResult(*sources)
        result.visit(visitor)
    except Exception as error:  # noqa: BLE001 - tolerate truncated/corrupt output.xml
        # Results/containers completed before the failure are already flushed by
        # the file logger; emit a warning rather than aborting so CI still gets a
        # partial Allure report.
        print(
            f"warning: stopped early while converting {sources!r}: {error}",
            file=sys.stderr,
        )
