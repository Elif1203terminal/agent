"""Tests for RuntimeTester — all mocked, zero real network or subprocess calls."""

import pytest
from unittest.mock import patch, MagicMock

from agents.runtime_tester import RuntimeTester
from agents.tester import TesterAgent
from core.state import PipelineState, FileEntry, Issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(stack="flask", files=None):
    state = PipelineState(request="test", category="web", stack=stack)
    state.current_files = [
        FileEntry(path=path, content=content,
                  language="python" if path.endswith(".py") else "html")
        for path, content in (files or {}).items()
    ]
    return state


def _mock_resp_obj(headers: dict):
    """Return a mock response with .headers.get() backed by the given dict."""
    resp = MagicMock()
    h = dict(headers)
    resp.headers.get = lambda k, d=None: h.get(k, d)
    return resp


def _setup_venv(tmp_path):
    """Create a fake venv python binary so os.path.isfile check passes."""
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    return str(tmp_path)


# ---------------------------------------------------------------------------
# TestSkipNonHttpStacks
# ---------------------------------------------------------------------------

class TestSkipNonHttpStacks:
    @pytest.mark.parametrize("stack", ["static", "cli", "data", "script"])
    def test_non_http_stack_returns_empty(self, stack):
        state = _make_state(stack)
        tester = RuntimeTester()
        with patch("subprocess.Popen") as mock_popen:
            result = tester.run(state, "/tmp/fake_work_dir")
        assert result == []
        mock_popen.assert_not_called()


# ---------------------------------------------------------------------------
# TestNoVenv
# ---------------------------------------------------------------------------

class TestNoVenv:
    def test_missing_venv_returns_empty(self, tmp_path):
        # .venv/bin/python does NOT exist → run() returns []
        state = _make_state("flask")
        tester = RuntimeTester()
        with patch("subprocess.Popen") as mock_popen:
            result = tester.run(state, str(tmp_path))
        assert result == []
        mock_popen.assert_not_called()


# ---------------------------------------------------------------------------
# TestServerLifecycle
# ---------------------------------------------------------------------------

class TestServerLifecycle:
    def test_popen_file_not_found_returns_empty(self, tmp_path):
        work_dir = _setup_venv(tmp_path)
        state = _make_state("flask")
        tester = RuntimeTester()
        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            result = tester.run(state, work_dir)
        assert result == []

    def test_popen_permission_error_returns_empty(self, tmp_path):
        work_dir = _setup_venv(tmp_path)
        state = _make_state("flask")
        tester = RuntimeTester()
        with patch("subprocess.Popen", side_effect=PermissionError):
            result = tester.run(state, work_dir)
        assert result == []

    def test_wait_ready_false_returns_startup_warning(self, tmp_path):
        work_dir = _setup_venv(tmp_path)
        state = _make_state("flask")
        tester = RuntimeTester()
        mock_proc = MagicMock()
        with patch("subprocess.Popen", return_value=mock_proc):
            with patch.object(tester, "_wait_ready", return_value=False):
                result = tester.run(state, work_dir)
        assert len(result) == 1
        assert result[0].severity == "warning"
        assert "did not start" in result[0].message

    def test_terminate_called_after_probes_complete(self, tmp_path):
        work_dir = _setup_venv(tmp_path)
        state = _make_state("flask")
        tester = RuntimeTester()
        mock_proc = MagicMock()
        with patch("subprocess.Popen", return_value=mock_proc):
            with patch.object(tester, "_wait_ready", return_value=True):
                with patch.object(tester, "_run_probes", return_value=[]):
                    tester.run(state, work_dir)
        mock_proc.terminate.assert_called_once()

    def test_terminate_called_even_when_probes_raise(self, tmp_path):
        work_dir = _setup_venv(tmp_path)
        state = _make_state("flask")
        tester = RuntimeTester()
        mock_proc = MagicMock()
        with patch("subprocess.Popen", return_value=mock_proc):
            with patch.object(tester, "_wait_ready", return_value=True):
                with patch.object(tester, "_run_probes", side_effect=RuntimeError("probe crash")):
                    with pytest.raises(RuntimeError):
                        tester.run(state, work_dir)
        mock_proc.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# TestProbeSecurityHeaders
# ---------------------------------------------------------------------------

class TestProbeSecurityHeaders:
    def test_all_three_headers_present_no_issues(self):
        tester = RuntimeTester()
        resp = _mock_resp_obj({
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "X-XSS-Protection": "1; mode=block",
        })
        with patch.object(tester, "_get", return_value=(resp, "OK", 200)):
            issues = tester._probe_security_headers("http://127.0.0.1:5000")
        assert issues == []

    def test_x_frame_options_missing_one_issue(self):
        tester = RuntimeTester()
        resp = _mock_resp_obj({
            "X-Content-Type-Options": "nosniff",
            "X-XSS-Protection": "1; mode=block",
        })
        with patch.object(tester, "_get", return_value=(resp, "OK", 200)):
            issues = tester._probe_security_headers("http://127.0.0.1:5000")
        assert len(issues) == 1
        assert "X-Frame-Options" in issues[0].message

    def test_all_headers_missing_three_issues(self):
        tester = RuntimeTester()
        resp = _mock_resp_obj({})
        with patch.object(tester, "_get", return_value=(resp, "OK", 200)):
            issues = tester._probe_security_headers("http://127.0.0.1:5000")
        assert len(issues) == 3
        assert all(i.severity == "warning" for i in issues)

    def test_server_500_still_checks_headers(self):
        tester = RuntimeTester()
        resp = _mock_resp_obj({})  # all headers missing on a 500
        with patch.object(tester, "_get", return_value=(resp, "Internal Server Error", 500)):
            issues = tester._probe_security_headers("http://127.0.0.1:5000")
        assert len(issues) == 3


# ---------------------------------------------------------------------------
# TestProbeDebugMode
# ---------------------------------------------------------------------------

class TestProbeDebugMode:
    def test_werkzeug_debugger_in_body_returns_error(self):
        tester = RuntimeTester()
        with patch.object(tester, "_get", return_value=(MagicMock(), "Werkzeug Debugger active", 404)):
            issues = tester._probe_debug_mode("http://127.0.0.1:5000")
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "Werkzeug Debugger" in issues[0].message

    def test_traceback_in_body_returns_error(self):
        tester = RuntimeTester()
        body = "Traceback (most recent call last):\n  File app.py line 1"
        with patch.object(tester, "_get", return_value=(MagicMock(), body, 500)):
            issues = tester._probe_debug_mode("http://127.0.0.1:5000")
        assert len(issues) == 1
        assert issues[0].severity == "error"

    def test_interactive_console_in_body_returns_error(self):
        tester = RuntimeTester()
        with patch.object(tester, "_get", return_value=(MagicMock(), "Interactive Console enabled", 500)):
            issues = tester._probe_debug_mode("http://127.0.0.1:5000")
        assert len(issues) == 1
        assert issues[0].severity == "error"

    def test_normal_404_body_no_issues(self):
        tester = RuntimeTester()
        with patch.object(tester, "_get", return_value=(MagicMock(), "Not Found", 404)):
            issues = tester._probe_debug_mode("http://127.0.0.1:5000")
        assert issues == []


# ---------------------------------------------------------------------------
# TestProbeCORSWildcard
# ---------------------------------------------------------------------------

class TestProbeCORSWildcard:
    def test_wildcard_cors_returns_warning(self):
        tester = RuntimeTester()
        resp = _mock_resp_obj({"Access-Control-Allow-Origin": "*"})
        with patch.object(tester, "_get", return_value=(resp, "OK", 200)):
            issues = tester._probe_cors_wildcard("http://127.0.0.1:5000")
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "wildcard" in issues[0].message.lower() or "*" in issues[0].message

    def test_specific_origin_no_issues(self):
        tester = RuntimeTester()
        resp = _mock_resp_obj({"Access-Control-Allow-Origin": "https://example.com"})
        with patch.object(tester, "_get", return_value=(resp, "OK", 200)):
            issues = tester._probe_cors_wildcard("http://127.0.0.1:5000")
        assert issues == []

    def test_no_cors_header_no_issues(self):
        tester = RuntimeTester()
        resp = _mock_resp_obj({})
        with patch.object(tester, "_get", return_value=(resp, "OK", 200)):
            issues = tester._probe_cors_wildcard("http://127.0.0.1:5000")
        assert issues == []


# ---------------------------------------------------------------------------
# TestProbeSensitivePaths
# ---------------------------------------------------------------------------

class TestProbeSensitivePaths:
    def test_env_exposed_returns_error(self):
        tester = RuntimeTester()

        def fake_get(url, headers=None, timeout=5):
            if "/.env" in url:
                return (MagicMock(), "SECRET=abc123", 200)
            return (MagicMock(), "Not Found", 404)

        with patch.object(tester, "_get", side_effect=fake_get):
            issues = tester._probe_sensitive_paths("http://127.0.0.1:5000")
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "/.env" in issues[0].message

    def test_env_404_no_issues(self):
        tester = RuntimeTester()
        with patch.object(tester, "_get", return_value=(MagicMock(), "Not Found", 404)):
            issues = tester._probe_sensitive_paths("http://127.0.0.1:5000")
        assert issues == []

    def test_multiple_sensitive_paths_exposed_one_issue_each(self):
        tester = RuntimeTester()
        # All paths return 200
        with patch.object(tester, "_get", return_value=(MagicMock(), "data", 200)):
            issues = tester._probe_sensitive_paths("http://127.0.0.1:5000")
        assert len(issues) == 4
        assert all(i.severity == "error" for i in issues)

    def test_all_sensitive_paths_404_no_issues(self):
        tester = RuntimeTester()
        with patch.object(tester, "_get", return_value=(MagicMock(), "Not Found", 404)):
            issues = tester._probe_sensitive_paths("http://127.0.0.1:5000")
        assert issues == []


# ---------------------------------------------------------------------------
# TestHelpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_find_entry_returns_first_matching_file(self):
        state = _make_state("flask", {"app.py": "x = 1", "main.py": "y = 2"})
        tester = RuntimeTester()
        entry = tester._find_entry(state, ["app.py", "main.py"])
        assert entry == "app.py"

    def test_find_entry_falls_back_to_first_candidate(self):
        state = _make_state("flask", {"other.py": "x = 1"})
        tester = RuntimeTester()
        entry = tester._find_entry(state, ["app.py", "main.py"])
        assert entry == "app.py"  # fallback: first candidate

    def test_get_connection_failure_returns_null_tuple(self):
        import urllib.error
        tester = RuntimeTester()
        with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError):
            resp, body, status = tester._get("http://127.0.0.1:9999/")
        assert resp is None
        assert body == ""
        assert status == -1


# ---------------------------------------------------------------------------
# TestRuntimeTesterWiredIntoTester
# ---------------------------------------------------------------------------

class TestRuntimeTesterWiredIntoTester:
    def test_runtime_issues_appended_to_test_issues(self, tmp_path):
        state = _make_state("flask")  # no .py files → no flake8 loop
        runtime_issue = Issue(
            source="runtime", severity="warning", file="app.py",
            line=None, message="Missing X-Frame-Options", suggestion="add it",
        )

        with patch("agents.tester.RuntimeTester") as MockRT, \
             patch("subprocess.run") as mock_run:
            MockRT.return_value.run.return_value = [runtime_issue]
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            agent = TesterAgent()
            result = agent.run(state, str(tmp_path))

        assert runtime_issue in result._test_issues

    def test_runtime_empty_results_in_no_runtime_issues(self, tmp_path):
        state = _make_state("flask")

        with patch("agents.tester.RuntimeTester") as MockRT, \
             patch("subprocess.run") as mock_run:
            MockRT.return_value.run.return_value = []
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            agent = TesterAgent()
            result = agent.run(state, str(tmp_path))

        runtime_issues = [i for i in result._test_issues if i.source == "runtime"]
        assert runtime_issues == []
