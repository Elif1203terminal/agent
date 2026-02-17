"""Tests for core.state models."""

from core.state import FileEntry, Issue, Iteration, PipelineState


def test_file_entry_creation():
    f = FileEntry(path="app.py", content="print('hi')", language="python")
    assert f.path == "app.py"
    assert f.language == "python"


def test_issue_creation():
    i = Issue(source="reviewer", severity="error", file="app.py",
              line=10, message="Missing import", suggestion="Add import os")
    assert i.severity == "error"
    assert i.line == 10


def test_issue_no_line():
    i = Issue(source="tester", severity="warning", file="app.py",
              line=None, message="Lint warning", suggestion="Fix it")
    assert i.line is None


def test_iteration_creation():
    files = [FileEntry(path="app.py", content="pass", language="python")]
    issues = [Issue(source="tester", severity="warning", file="app.py",
                    line=1, message="W001", suggestion="fix")]
    it = Iteration(number=1, files=files, issues=issues,
                   lint_passed=True, tests_passed=True, security_passed=True)
    assert it.number == 1
    assert len(it.files) == 1
    assert len(it.issues) == 1


def test_pipeline_state_defaults():
    state = PipelineState(request="build a web app")
    assert state.request == "build a web app"
    assert state.status == "planning"
    assert state.max_iterations == 2
    assert state.iterations == []
    assert state.current_files == []
    assert state.category == ""


def test_pipeline_state_custom():
    state = PipelineState(request="test", max_iterations=5, category="web")
    assert state.max_iterations == 5
    assert state.category == "web"
