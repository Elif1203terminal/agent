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


def test_security_autofix_debug():
    """Security agent auto-fixes debug=True."""
    from agents.security import SecurityAgent
    from core.state import PipelineState

    state = PipelineState(request="test")
    state.current_files = [
        FileEntry(path="app.py", content="app.run(debug=True, port=5000)", language="python")
    ]

    agent = SecurityAgent()
    agent.run(state)

    assert "debug=False" in state.current_files[0].content
    assert "debug=True" not in state.current_files[0].content


def test_security_autofix_bind_address():
    """Security agent auto-fixes 0.0.0.0 binding."""
    from agents.security import SecurityAgent
    from core.state import PipelineState

    state = PipelineState(request="test")
    state.current_files = [
        FileEntry(path="app.py", content="app.run(host='0.0.0.0', port=5000)", language="python")
    ]

    agent = SecurityAgent()
    agent.run(state)

    assert "'127.0.0.1'" in state.current_files[0].content
    assert "'0.0.0.0'" not in state.current_files[0].content


def test_security_autofix_leaves_no_warnings_for_fixed():
    """After auto-fix, the fixed patterns should not appear as issues."""
    from agents.security import SecurityAgent
    from core.state import PipelineState

    state = PipelineState(request="test")
    state.current_files = [
        FileEntry(path="app.py", content="app.run(debug=True, host='0.0.0.0')", language="python")
    ]

    agent = SecurityAgent()
    agent.run(state)

    security_issues = state._security_issues
    # No warnings should remain for debug or 0.0.0.0 since both were auto-fixed
    debug_issues = [i for i in security_issues if "debug" in i.message.lower()]
    bind_issues = [i for i in security_issues if "0.0.0.0" in i.message]
    assert len(debug_issues) == 0
    assert len(bind_issues) == 0
