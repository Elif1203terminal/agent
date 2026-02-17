"""Tests for core.orchestrator — mock LLM calls, verify loop logic."""

from unittest.mock import patch, MagicMock
from core.orchestrator import Orchestrator
from core.state import PipelineState, FileEntry, Issue, Iteration


def _mock_planner_run(state):
    state.spec = "Build a simple hello world app"
    state.file_manifest = ["app.py"]
    state.stack = "script"
    state.status = "planning"
    return state


def _mock_generator_run(state):
    state.current_files = [
        FileEntry(path="app.py", content="print('hello')", language="python")
    ]
    state.status = "generating"
    return state


def _mock_reviewer_run(state):
    state._review_issues = []
    state.status = "reviewing"
    return state


def _mock_tester_run(state, work_dir):
    state._test_issues = []
    state._lint_passed = True
    state._tests_passed = True
    state.status = "testing"
    return state


def _mock_security_run(state):
    state._security_issues = []
    state.status = "security"
    return state


def _mock_patch_run(state, issues):
    state.patch_instructions = ""
    return state


def test_create_state():
    orch = Orchestrator()
    state = orch.create_state("build a web app", category="web")
    assert state.category == "web"
    assert state.request == "build a web app"
    assert state.max_iterations == 2


def test_create_state_auto_classify():
    orch = Orchestrator()
    state = orch.create_state("create a REST API with FastAPI")
    assert state.category == "api"


@patch("core.orchestrator.Orchestrator.__init__", lambda self: None)
def test_run_iteration_all_pass():
    orch = Orchestrator()
    orch.planner = MagicMock()
    orch.generator = MagicMock(side_effect=lambda: None)
    orch.generator.run = _mock_generator_run
    orch.reviewer = MagicMock()
    orch.reviewer.run = _mock_reviewer_run
    orch.tester = MagicMock()
    orch.tester.run = _mock_tester_run
    orch.security = MagicMock()
    orch.security.run = _mock_security_run
    orch.patch_composer = MagicMock()
    orch.patch_composer.run = _mock_patch_run

    state = PipelineState(request="test", category="script", stack="script")
    state = orch.run_iteration(state)

    assert state.status == "done"
    assert len(state.iterations) == 1
    assert state.iterations[0].lint_passed is True


@patch("core.orchestrator.Orchestrator.__init__", lambda self: None)
def test_run_iteration_with_errors():
    orch = Orchestrator()
    orch.generator = MagicMock()
    orch.generator.run = _mock_generator_run

    def reviewer_with_error(state):
        state._review_issues = [
            Issue(source="reviewer", severity="error", file="app.py",
                  line=1, message="Missing import", suggestion="Add import")
        ]
        return state

    orch.reviewer = MagicMock()
    orch.reviewer.run = reviewer_with_error
    orch.tester = MagicMock()
    orch.tester.run = _mock_tester_run
    orch.security = MagicMock()
    orch.security.run = _mock_security_run
    orch.patch_composer = MagicMock()
    orch.patch_composer.run = _mock_patch_run

    state = PipelineState(request="test", category="script", stack="script")
    state = orch.run_iteration(state)

    assert state.status == "awaiting_approval"
    assert len(state.iterations[0].issues) == 1


def test_run_full_no_callback_stops_after_one():
    """Without a callback, pipeline runs one iteration and stops."""
    orch = Orchestrator()

    with patch.object(orch, "plan", side_effect=_mock_planner_run), \
         patch.object(orch.generator, "run", side_effect=_mock_generator_run), \
         patch.object(orch.reviewer, "run", side_effect=_mock_reviewer_run), \
         patch.object(orch.tester, "run", side_effect=_mock_tester_run), \
         patch.object(orch.security, "run", side_effect=_mock_security_run), \
         patch.object(orch.patch_composer, "run", side_effect=_mock_patch_run):

        state = orch.run_full("test request", category="script")
        assert state.status == "done"
        assert len(state.iterations) == 1


def test_hard_max_caps_user_input():
    """User cannot exceed the hard_max_iterations ceiling."""
    from config.defaults import DEFAULTS
    hard_max = DEFAULTS["hard_max_iterations"]

    orch = Orchestrator()
    state = orch.create_state("test", max_iterations=999)
    assert state.max_iterations == hard_max


def test_run_iteration_refuses_past_max():
    """run_iteration returns immediately if already at max_iterations."""
    orch = Orchestrator()
    state = PipelineState(request="test", category="script", stack="script",
                          max_iterations=1)
    # Simulate one iteration already done
    state.iterations.append(
        Iteration(number=1, files=[], issues=[],
                  lint_passed=True, tests_passed=True, security_passed=True)
    )
    state.status = "awaiting_approval"

    state = orch.run_iteration(state)
    assert state.status == "done"
    assert len(state.iterations) == 1  # no new iteration added
