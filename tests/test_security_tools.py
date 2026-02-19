"""Tests for security agent tool integration and framework-aware behaviour."""

from unittest.mock import patch, MagicMock
from agents.security import SecurityAgent
from core.state import PipelineState, FileEntry


def _make_state(stack="flask", files=None):
    state = PipelineState(request="test", category="web", stack=stack)
    state.current_files = [
        FileEntry(path=path, content=content,
                  language="python" if path.endswith(".py") else "html")
        for path, content in (files or {}).items()
    ]
    return state


def _run(stack="flask", files=None):
    agent = SecurityAgent()
    state = _make_state(stack=stack, files=files)
    state = agent.run(state)
    return state._security_issues


def _msgs(stack="flask", files=None):
    return [i.message for i in _run(stack=stack, files=files)]


# ---------------------------------------------------------------------------
# CSRF — stack-aware behaviour
# ---------------------------------------------------------------------------

class TestCSRFStackAware:
    def test_csrf_flagged_for_flask(self):
        html = '<form method="post"><input name="email"></form>'
        msgs = _msgs("flask", {"templates/form.html": html})
        assert any("CSRF" in m for m in msgs)

    def test_csrf_not_flagged_for_fastapi_jwt(self):
        """FastAPI uses JWT in Authorization header — no CSRF risk."""
        html = '<form method="post"><input name="email"></form>'
        msgs = _msgs("fastapi", {"templates/form.html": html})
        assert not any("CSRF" in m for m in msgs)

    def test_csrf_not_flagged_for_static(self):
        """Static sites have no server-side session — no CSRF risk."""
        html = '<form method="post"><input name="q"></form>'
        msgs = _msgs("static", {"index.html": html})
        assert not any("CSRF" in m for m in msgs)

    def test_csrf_flagged_flask_post_no_token(self):
        html = '<form method="POST"><input name="data"></form>'
        msgs = _msgs("flask", {"templates/form.html": html})
        assert any("CSRF" in m for m in msgs)

    def test_csrf_clean_flask_with_hidden_tag(self):
        html = '<form method="post">{{ form.hidden_tag() }}<input name="data"></form>'
        msgs = _msgs("flask", {"templates/form.html": html})
        assert not any("CSRF" in m for m in msgs)

    def test_csrf_clean_flask_with_csrf_token(self):
        html = '<form method="post">{{ csrf_token() }}<input name="data"></form>'
        msgs = _msgs("flask", {"templates/form.html": html})
        assert not any("CSRF" in m for m in msgs)


# ---------------------------------------------------------------------------
# pip-audit: CVE scanning
# ---------------------------------------------------------------------------

class TestPipAudit:
    def test_skipped_when_no_requirements(self):
        """No requirements.txt — pip-audit should not run or error."""
        agent = SecurityAgent()
        state = _make_state("flask", {"app.py": "print('hello')"})
        result = agent._run_pip_audit(state)
        assert result == []

    def test_skipped_when_not_installed(self):
        """pip-audit not installed — should degrade gracefully."""
        agent = SecurityAgent()
        state = _make_state("flask", {"requirements.txt": "flask==2.0.0"})
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = agent._run_pip_audit(state)
        assert result == []

    def test_skipped_on_timeout(self):
        import subprocess
        agent = SecurityAgent()
        state = _make_state("flask", {"requirements.txt": "flask==2.0.0"})
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pip-audit", 60)):
            result = agent._run_pip_audit(state)
        assert result == []

    def test_cve_found_returns_issue(self):
        """When pip-audit returns a CVE, it should become an Issue."""
        import json
        vuln_output = json.dumps({
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.25.0",
                    "vulns": [
                        {
                            "id": "CVE-2023-32681",
                            "description": "Unintended leak of Proxy-Authorization header",
                            "fix_versions": ["2.31.0"],
                        }
                    ],
                }
            ]
        })
        mock_result = MagicMock()
        mock_result.stdout = vuln_output
        mock_result.returncode = 1

        agent = SecurityAgent()
        state = _make_state("flask", {"requirements.txt": "requests==2.25.0"})
        with patch("subprocess.run", return_value=mock_result):
            issues = agent._run_pip_audit(state)

        assert len(issues) == 1
        assert issues[0].source == "security"
        assert issues[0].severity == "error"
        assert "CVE-2023-32681" in issues[0].message
        assert issues[0].file == "requirements.txt"

    def test_malformed_json_does_not_crash(self):
        mock_result = MagicMock()
        mock_result.stdout = "this is not json"
        mock_result.returncode = 1

        agent = SecurityAgent()
        state = _make_state("flask", {"requirements.txt": "flask==2.0.0"})
        with patch("subprocess.run", return_value=mock_result):
            result = agent._run_pip_audit(state)
        assert result == []

    def test_no_vulns_returns_empty(self):
        import json
        clean_output = json.dumps({
            "dependencies": [
                {"name": "flask", "version": "3.0.0", "vulns": []}
            ]
        })
        mock_result = MagicMock()
        mock_result.stdout = clean_output
        mock_result.returncode = 0

        agent = SecurityAgent()
        state = _make_state("flask", {"requirements.txt": "flask==3.0.0"})
        with patch("subprocess.run", return_value=mock_result):
            issues = agent._run_pip_audit(state)
        assert issues == []


# ---------------------------------------------------------------------------
# semgrep: optional static analysis
# ---------------------------------------------------------------------------

class TestSemgrep:
    def test_skipped_when_not_installed(self):
        agent = SecurityAgent()
        state = _make_state("flask", {"app.py": "x = 1"})
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = agent._run_semgrep(state)
        assert result == []

    def test_skipped_on_timeout(self):
        import subprocess
        agent = SecurityAgent()
        state = _make_state("flask", {"app.py": "x = 1"})
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("semgrep", 60)):
            result = agent._run_semgrep(state)
        assert result == []

    def test_skipped_when_no_python_files(self):
        agent = SecurityAgent()
        state = _make_state("static", {"index.html": "<h1>Hello</h1>"})
        result = agent._run_semgrep(state)
        assert result == []

    def test_finding_becomes_issue(self):
        import json
        import os
        finding_output = json.dumps({
            "results": [
                {
                    "check_id": "python.lang.security.audit.eval-detected",
                    "path": "/tmp/PLACEHOLDER/app.py",
                    "start": {"line": 5},
                    "extra": {
                        "message": "Detected use of eval()",
                        "severity": "ERROR",
                    },
                }
            ]
        })
        mock_result = MagicMock()
        mock_result.stdout = finding_output

        agent = SecurityAgent()
        state = _make_state("flask", {"app.py": "eval(user_input)"})

        with patch("subprocess.run", return_value=mock_result), \
             patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            mock_tmpdir.return_value.__enter__ = lambda s: "/tmp/PLACEHOLDER"
            mock_tmpdir.return_value.__exit__ = MagicMock(return_value=False)
            with patch("os.makedirs"), patch("builtins.open", MagicMock()):
                issues = agent._run_semgrep(state)

        assert len(issues) == 1
        assert issues[0].source == "semgrep"
        assert issues[0].severity == "error"
        assert "eval" in issues[0].message.lower()

    def test_malformed_json_does_not_crash(self):
        mock_result = MagicMock()
        mock_result.stdout = "not json"

        agent = SecurityAgent()
        state = _make_state("flask", {"app.py": "x = 1"})
        with patch("subprocess.run", return_value=mock_result), \
             patch("os.makedirs"), patch("builtins.open", MagicMock()):
            result = agent._run_semgrep(state)
        assert result == []


# ---------------------------------------------------------------------------
# HTTPS pattern
# ---------------------------------------------------------------------------

class TestHTTPSPattern:
    def test_app_run_without_ssl_flagged(self):
        msgs = _msgs("flask", {"app.py": "app.run(debug=False, port=5000)"})
        assert any("ssl" in m.lower() or "TLS" in m or "encrypted" in m.lower() for m in msgs)

    def test_app_run_with_ssl_context_clean(self):
        msgs = _msgs("flask", {"app.py": "app.run(ssl_context='adhoc')"})
        ssl_msgs = [m for m in msgs if "ssl" in m.lower() and "encrypted" in m.lower()]
        assert len(ssl_msgs) == 0
