"""Generate Allure input files from Robot Framework results.

This package walks a Robot Framework ``output.xml`` using the Robot Framework
``ResultVisitor`` API and emits Allure result files. It is an alternative to the
``allure-robotframework`` listener: instead of hooking into a live test run, it
post-processes an existing ``output.xml`` (and merges several of them natively).
"""

from robotframework_allurevisitor.visitor import AllureResultVisitor, generate

__all__ = ["AllureResultVisitor", "generate"]
