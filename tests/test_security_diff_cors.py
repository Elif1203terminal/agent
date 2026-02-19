"""Tests for scan_diff(), _scan_patch_drift(), and CORS wildcard patterns."""

from unittest.mock import patch, MagicMock
from agents.security import SecurityAgent
from core.state import PipelineState, FileEntry, Iteration, Issue


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


def _file_entries(files: dict) -> list:
    return [
        FileEntry(path=p, content=c, language="python" if p.endswith(".py") else "html")
        for p, c in files.items()
    ]


def _make_iteration(files: dict) -> Iteration:
    return Iteration(
        number=1,
        files=_file_entries(files),
        issues=[],
        lint_passed=True,
        tests_passed=True,
        security_passed=True,
    )


# ---------------------------------------------------------------------------
# scan_diff(): public method for commit hooks
# ---------------------------------------------------------------------------

class TestScanDiff:
    def _diff(self, added_line: str, filepath: str = "app.py") -> str:
        return (
            f"--- a/{filepath}\n"
            f"+++ b/{filepath}\n"
            f"@@ -1,3 +1,4 @@\n"
            f" existing line\n"
            f"+{added_line}\n"
            f" another existing line\n"
        )

    def test_hardcoded_secret_in_diff_flagged(self):
        agent = SecurityAgent()
        diff = self._diff('SECRET_KEY = "my-hard-coded-secret"')
        issues = agent.scan_diff(diff)
        assert any("secret" in i.message.lower() or "SECRET_KEY" in i.message for i in issues)

    def test_hardcoded_password_in_diff_flagged(self):
        agent = SecurityAgent()
        diff = self._diff('password = "hunter2"')
        issues = agent.scan_diff(diff)
        assert len(issues) >= 1
        assert all(i.source == "security" for i in issues)

    def test_eval_in_diff_flagged(self):
        agent = SecurityAgent()
        diff = self._diff("result = eval(user_input)")
        issues = agent.scan_diff(diff)
        assert any("eval" in i.message.lower() for i in issues)

    def test_clean_line_not_flagged(self):
        agent = SecurityAgent()
        diff = self._diff("x = 42")
        issues = agent.scan_diff(diff)
        assert issues == []

    def test_removed_line_not_flagged(self):
        """Minus lines (deletions) should never produce issues."""
        agent = SecurityAgent()
        diff = (
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,3 +1,2 @@\n"
            "-password = 'old_secret'\n"
            " x = 1\n"
            " y = 2\n"
        )
        issues = agent.scan_diff(diff)
        assert issues == []

    def test_context_line_not_flagged(self):
        """Context lines (no prefix) should not be flagged."""
        agent = SecurityAgent()
        diff = (
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,3 +1,4 @@\n"
            " password = 'existing_secret'\n"
            "+x = 1\n"
            " y = 2\n"
        )
        issues = agent.scan_diff(diff)
        # Only "+x = 1" is scanned — clean, so no issues
        assert issues == []

    def test_issue_message_prefixed_with_diff(self):
        agent = SecurityAgent()
        diff = self._diff('SECRET_KEY = "abc123"')
        issues = agent.scan_diff(diff)
        assert any(i.message.startswith("[diff]") for i in issues)

    def test_correct_file_attributed(self):
        agent = SecurityAgent()
        diff = (
            "--- a/config/settings.py\n"
            "+++ b/config/settings.py\n"
            "@@ -1,2 +1,3 @@\n"
            " x = 1\n"
            '+SECRET_KEY = "hardcoded"\n'
        )
        issues = agent.scan_diff(diff)
        assert len(issues) >= 1
        assert issues[0].file == "config/settings.py"

    def test_multiple_files_in_diff(self):
        agent = SecurityAgent()
        diff = (
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,1 +1,2 @@\n"
            " x = 1\n"
            '+eval(user_input)\n'
            "--- a/utils.py\n"
            "+++ b/utils.py\n"
            "@@ -1,1 +1,2 @@\n"
            " y = 2\n"
            '+password = "secret"\n'
        )
        issues = agent.scan_diff(diff)
        files = {i.file for i in issues}
        assert "app.py" in files
        assert "utils.py" in files

    def test_shell_true_in_diff_flagged(self):
        agent = SecurityAgent()
        diff = self._diff("subprocess.run(cmd, shell=True)")
        issues = agent.scan_diff(diff)
        assert any("shell" in i.message.lower() for i in issues)

    def test_cors_wildcard_in_diff_flagged(self):
        agent = SecurityAgent()
        diff = self._diff('allow_origins=["*"]')
        issues = agent.scan_diff(diff)
        assert any("CORS" in i.message or "wildcard" in i.message.lower() for i in issues)

    def test_empty_diff_returns_empty(self):
        agent = SecurityAgent()
        issues = agent.scan_diff("")
        assert issues == []

    def test_diff_with_no_additions_returns_empty(self):
        agent = SecurityAgent()
        diff = (
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,1 @@\n"
            "-password = 'old'\n"
            " x = 1\n"
        )
        issues = agent.scan_diff(diff)
        assert issues == []


# ---------------------------------------------------------------------------
# _scan_patch_drift(): detects secrets newly added between iterations
# ---------------------------------------------------------------------------

class TestScanPatchDrift:
    def test_newly_added_secret_flagged(self):
        """A secret added in the patch iteration is flagged even if not in prev iteration."""
        agent = SecurityAgent()
        state = _make_state("flask", {"app.py": 'SECRET_KEY = "hardcoded"\nx = 1\n'})
        # Previous iteration had clean file
        state.iterations = [_make_iteration({"app.py": "x = 1\n"})]
        issues = agent._scan_patch_drift(state)
        assert any("secret" in i.message.lower() or "SECRET_KEY" in i.message for i in issues)

    def test_secret_present_in_both_iterations_not_double_flagged(self):
        """A secret that existed before the patch is not re-reported by drift scan."""
        agent = SecurityAgent()
        # Same content in both — no new additions
        content = 'SECRET_KEY = "hardcoded"\n'
        state = _make_state("flask", {"app.py": content})
        state.iterations = [_make_iteration({"app.py": content})]
        issues = agent._scan_patch_drift(state)
        assert issues == []

    def test_clean_addition_not_flagged(self):
        agent = SecurityAgent()
        state = _make_state("flask", {"app.py": "x = 1\ny = 2\n"})
        state.iterations = [_make_iteration({"app.py": "x = 1\n"})]
        issues = agent._scan_patch_drift(state)
        assert issues == []

    def test_new_file_in_patch_scanned(self):
        """A file that didn't exist in the previous iteration is fully scanned."""
        agent = SecurityAgent()
        state = _make_state("flask", {"config.py": 'password = "secret123"\n'})
        state.iterations = [_make_iteration({})]  # config.py did not exist before
        issues = agent._scan_patch_drift(state)
        assert len(issues) >= 1

    def test_unchanged_file_skipped(self):
        """Files that are identical to the previous iteration are not scanned."""
        agent = SecurityAgent()
        content = "x = 1\n"
        state = _make_state("flask", {"app.py": content})
        state.iterations = [_make_iteration({"app.py": content})]
        issues = agent._scan_patch_drift(state)
        assert issues == []

    def test_drift_issue_message_prefixed(self):
        agent = SecurityAgent()
        state = _make_state("flask", {"app.py": 'SECRET_KEY = "new"\nx = 1\n'})
        state.iterations = [_make_iteration({"app.py": "x = 1\n"})]
        issues = agent._scan_patch_drift(state)
        assert all(i.message.startswith("[patch-drift]") for i in issues)

    def test_no_iterations_returns_empty(self):
        """With no previous iterations there is nothing to diff."""
        agent = SecurityAgent()
        state = _make_state("flask", {"app.py": 'SECRET_KEY = "hardcoded"\n'})
        # state.iterations is empty — drift scan should not be called
        issues = agent._scan_patch_drift(state)
        assert issues == []

    def test_drift_scan_wired_into_run(self):
        """When state.iterations is non-empty, run() calls _scan_patch_drift."""
        agent = SecurityAgent()
        # Clean current file — no whole-file issues
        state = _make_state("flask", {"app.py": 'SECRET_KEY = "injected"\nx = 1\n'})
        state.iterations = [_make_iteration({"app.py": "x = 1\n"})]
        # Suppress optional tool runners
        with patch.object(agent, "_run_pip_audit", return_value=[]), \
             patch.object(agent, "_run_semgrep", return_value=[]):
            state = agent.run(state)
        drift_issues = [i for i in state._security_issues if "[patch-drift]" in i.message]
        assert len(drift_issues) >= 1


# ---------------------------------------------------------------------------
# CORS wildcard patterns in config/rules.py
# ---------------------------------------------------------------------------

class TestCORSPatterns:
    def _run(self, code: str):
        state = _make_state("fastapi", {"main.py": code})
        agent = SecurityAgent()
        with patch.object(agent, "_run_pip_audit", return_value=[]), \
             patch.object(agent, "_run_semgrep", return_value=[]):
            state = agent.run(state)
        return [i.message for i in state._security_issues]

    def test_cors_wildcard_allow_origins_flagged(self):
        code = 'app.add_middleware(CORSMiddleware, allow_origins=["*"])\n'
        msgs = self._run(code)
        assert any("CORS" in m or "wildcard" in m.lower() for m in msgs)

    def test_cors_wildcard_single_quote_flagged(self):
        code = "app.add_middleware(CORSMiddleware, allow_origins=['*'])\n"
        msgs = self._run(code)
        assert any("CORS" in m or "wildcard" in m.lower() for m in msgs)

    def test_cors_explicit_origin_clean(self):
        code = 'app.add_middleware(CORSMiddleware, allow_origins=["https://example.com"])\n'
        msgs = self._run(code)
        assert not any("wildcard" in m.lower() for m in msgs)

    def test_cors_app_no_origins_flagged(self):
        """CORS(app) with no keyword args — permissive default."""
        code = "CORS(app)\n"
        msgs = self._run(code)
        assert any("CORS" in m for m in msgs)

    def test_cors_middleware_no_origins_flagged(self):
        """CORSMiddleware added without allow_origins."""
        code = "app.add_middleware(CORSMiddleware)\n"
        msgs = self._run(code)
        assert any("CORS" in m for m in msgs)

    def test_cors_with_env_origins_clean(self):
        """Reading origins from env var — acceptable pattern."""
        code = (
            'origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")\n'
            'app.add_middleware(CORSMiddleware, allow_origins=origins)\n'
        )
        msgs = self._run(code)
        # Should NOT flag the env-var pattern as wildcard
        assert not any("wildcard" in m.lower() for m in msgs)
