"""Tests for core.quality."""

from core.quality import quality_gates_pass
from core.state import Iteration, Issue, FileEntry


def _make_iteration(issues=None, lint_passed=True, tests_passed=True, security_passed=True):
    return Iteration(
        number=1,
        files=[FileEntry(path="app.py", content="pass", language="python")],
        issues=issues or [],
        lint_passed=lint_passed,
        tests_passed=tests_passed,
        security_passed=security_passed,
    )


def test_all_pass():
    it = _make_iteration()
    assert quality_gates_pass(it) is True


def test_error_fails():
    issues = [Issue(source="reviewer", severity="error", file="app.py",
                    line=1, message="broken", suggestion="fix")]
    it = _make_iteration(issues=issues)
    assert quality_gates_pass(it) is False


def test_warning_passes():
    issues = [Issue(source="reviewer", severity="warning", file="app.py",
                    line=1, message="minor", suggestion="maybe fix")]
    it = _make_iteration(issues=issues)
    assert quality_gates_pass(it) is True


def test_lint_failure():
    it = _make_iteration(lint_passed=False)
    assert quality_gates_pass(it) is False


def test_security_failure():
    it = _make_iteration(security_passed=False)
    assert quality_gates_pass(it) is False


def test_multiple_issues_mixed():
    issues = [
        Issue(source="reviewer", severity="warning", file="app.py",
              line=1, message="w1", suggestion="s1"),
        Issue(source="security", severity="info", file="app.py",
              line=2, message="i1", suggestion="s2"),
    ]
    it = _make_iteration(issues=issues)
    assert quality_gates_pass(it) is True
