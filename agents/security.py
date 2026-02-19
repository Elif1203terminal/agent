"""Security agent — static analysis, optional tool runners. Zero mandatory LLM calls."""

import difflib
import json
import os
import re
import subprocess
import tempfile

from core.state import PipelineState, Issue
from config.rules import SECURITY_PATTERNS, HTML_SECURITY_PATTERNS

# All pattern tuples we scan against (Python and HTML/template patterns combined)
_ALL_PATTERNS = SECURITY_PATTERNS + HTML_SECURITY_PATTERNS

_TEMPLATE_EXTENSIONS = {".html", ".jinja2", ".j2"}

# Stacks where CSRF on POST forms is required (cookie-based session auth)
_COOKIE_AUTH_STACKS = {"flask"}

# Stacks where CSRF is not required (JWT in Authorization header)
_JWT_AUTH_STACKS = {"fastapi"}


class SecurityAgent:
    """Runs static pattern checks, optional semgrep, and optional pip-audit CVE scan.

    Tool runners degrade gracefully — if semgrep or pip-audit are not installed,
    those checks are silently skipped. The core regex scanning always runs.
    """

    name = "security"

    def run(self, state: PipelineState) -> PipelineState:
        state.status = "security"
        issues = []
        fixes_applied = 0

        # --- Static pattern scanning ---
        for f in state.current_files:
            ext = "." + f.path.rsplit(".", 1)[-1] if "." in f.path else ""

            if f.path.endswith(".py"):
                # First pass: auto-fix what we can
                content = f.content
                for pattern, severity, message, suggestion, fix_from, fix_to in SECURITY_PATTERNS:
                    if fix_from and fix_to and fix_from.search(content):
                        content = fix_from.sub(fix_to, content)
                        fixes_applied += 1

                if content != f.content:
                    f.content = content

                # Second pass: scan for remaining issues (after fixes)
                lines = f.content.split("\n")
                for line_num, line in enumerate(lines, 1):
                    for pattern, severity, message, suggestion, fix_from, fix_to in SECURITY_PATTERNS:
                        if pattern.search(line):
                            issues.append(Issue(
                                source="security",
                                severity=severity,
                                file=f.path,
                                line=line_num,
                                message=message,
                                suggestion=suggestion,
                            ))

            elif ext in _TEMPLATE_EXTENSIONS:
                # Scan HTML/Jinja2 templates
                lines = f.content.split("\n")
                for line_num, line in enumerate(lines, 1):
                    for pattern, severity, message, suggestion, fix_from, fix_to in HTML_SECURITY_PATTERNS:
                        if pattern.search(line):
                            issues.append(Issue(
                                source="security",
                                severity=severity,
                                file=f.path,
                                line=line_num,
                                message=message,
                                suggestion=suggestion,
                            ))

                # CSRF check: only relevant for cookie-based auth stacks
                if state.stack in _COOKIE_AUTH_STACKS:
                    csrf_issue = self._check_csrf(f)
                    if csrf_issue:
                        issues.append(csrf_issue)

        # --- Optional tool runners ---
        issues.extend(self._run_pip_audit(state))
        issues.extend(self._run_semgrep(state))

        # --- Patch-mode drift scan: catch newly introduced secrets ---
        if state.iterations:
            issues.extend(self._scan_patch_drift(state))

        if fixes_applied:
            state._security_fixes_applied = fixes_applied

        state._security_issues = issues
        return state

    # ------------------------------------------------------------------
    # CSRF check
    # ------------------------------------------------------------------

    def _check_csrf(self, f) -> Issue | None:
        """Flag a template that has a POST form but no CSRF token anywhere in the file.

        Only called for cookie-based auth stacks (Flask). JWT-based stacks (FastAPI)
        do not need CSRF tokens because the token travels in the Authorization header,
        not in a cookie that browsers attach automatically.
        """
        has_post_form = re.search(
            r"""<\s*form\b[^>]+method\s*=\s*["']post["']""",
            f.content, re.IGNORECASE
        )
        if not has_post_form:
            return None
        has_csrf = re.search(r"""csrf|hidden_tag""", f.content, re.IGNORECASE)
        if has_csrf:
            return None
        return Issue(
            source="security",
            severity="error",
            file=f.path,
            line=None,
            message="POST form found with no CSRF protection",
            suggestion="Add {{ form.hidden_tag() }} (Flask-WTF) or {{ csrf_token() }} inside every POST form",
        )

    # ------------------------------------------------------------------
    # pip-audit: dependency CVE scanning
    # ------------------------------------------------------------------

    def _run_pip_audit(self, state: PipelineState) -> list:
        """Scan requirements.txt for known CVEs using pip-audit.

        Silently skipped if pip-audit is not installed or requirements.txt is absent.
        """
        req_file = next(
            (f for f in state.current_files if f.path == "requirements.txt"), None
        )
        if not req_file or not req_file.content.strip():
            return []

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as tmp:
            tmp.write(req_file.content)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                ["pip-audit", "-r", tmp_path, "--format", "json", "--no-deps"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []  # pip-audit not installed or timed out
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        issues = []
        try:
            data = json.loads(result.stdout)
            for dep in data.get("dependencies", []):
                for vuln in dep.get("vulns", []):
                    issues.append(Issue(
                        source="security",
                        severity="error",
                        file="requirements.txt",
                        line=None,
                        message=(
                            f"CVE in dependency {dep['name']}=={dep.get('version', '?')}: "
                            f"{vuln.get('id', '')} — {vuln.get('description', '')[:120]}"
                        ),
                        suggestion=(
                            f"Upgrade {dep['name']} to a patched version. "
                            f"See: {vuln.get('fix_versions', 'check PyPI advisory')}"
                        ),
                    ))
        except (json.JSONDecodeError, KeyError):
            pass

        return issues

    # ------------------------------------------------------------------
    # semgrep: rule-based static analysis
    # ------------------------------------------------------------------

    def _run_semgrep(self, state: PipelineState) -> list:
        """Run semgrep security rules over all Python files.

        Uses the built-in p/python and p/security-audit rule packs.
        Silently skipped if semgrep is not installed.

        semgrep install: pip install semgrep
        """
        py_files = [f for f in state.current_files if f.path.endswith(".py")]
        if not py_files:
            return []

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write Python files to temp dir
            for f in py_files:
                fpath = os.path.join(tmpdir, f.path)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "w") as fp:
                    fp.write(f.content)

            try:
                result = subprocess.run(
                    [
                        "semgrep",
                        "--config", "p/python",
                        "--config", "p/security-audit",
                        "--json",
                        "--quiet",
                        tmpdir,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return []  # semgrep not installed or timed out

        issues = []
        try:
            data = json.loads(result.stdout)
            for finding in data.get("results", []):
                # Map semgrep path back to relative path
                raw_path = finding.get("path", "")
                rel_path = os.path.relpath(raw_path, tmpdir) if tmpdir in raw_path else raw_path

                check_id = finding.get("check_id", "")
                msg = finding.get("extra", {}).get("message", check_id)
                line = finding.get("start", {}).get("line")
                severity_raw = finding.get("extra", {}).get("severity", "WARNING").upper()
                severity = "error" if severity_raw == "ERROR" else "warning"

                issues.append(Issue(
                    source="semgrep",
                    severity=severity,
                    file=rel_path,
                    line=line,
                    message=f"[semgrep] {msg}",
                    suggestion=f"Rule: {check_id} — review and fix the flagged pattern",
                ))
        except (json.JSONDecodeError, KeyError):
            pass

        return issues

    # ------------------------------------------------------------------
    # Patch-mode drift scan: detect secrets newly added between iterations
    # ------------------------------------------------------------------

    def _scan_patch_drift(self, state: PipelineState) -> list:
        """Compare current files to the previous iteration, scan only added lines.

        This catches secrets or unsafe patterns introduced by a patch that would
        otherwise be missed because the whole-file scan already ran (and may have
        auto-fixed them in the previous iteration, masking a regression).
        """
        if not state.iterations:
            return []
        prev_files = {f.path: f.content for f in state.iterations[-1].files}
        issues = []

        for f in state.current_files:
            old_content = prev_files.get(f.path, "")
            if old_content == f.content:
                continue  # unchanged file

            old_lines = old_content.splitlines(keepends=True)
            new_lines = f.content.splitlines(keepends=True)

            matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
            added_lines = []
            for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
                if tag in ("insert", "replace"):
                    for idx, line in enumerate(new_lines[j1:j2], start=j1 + 1):
                        added_lines.append((idx, line.rstrip("\n")))

            for line_num, line in added_lines:
                for pattern, severity, message, suggestion, _ff, _ft in _ALL_PATTERNS:
                    if pattern.search(line):
                        issues.append(Issue(
                            source="security",
                            severity=severity,
                            file=f.path,
                            line=line_num,
                            message=f"[patch-drift] {message}",
                            suggestion=suggestion,
                        ))
                        break  # one issue per added line is enough

        return issues

    # ------------------------------------------------------------------
    # Public API: scan a unified diff string (for commit hooks / CI)
    # ------------------------------------------------------------------

    def scan_diff(self, diff_text: str) -> list:
        """Scan a unified diff for security issues in added lines only.

        Designed for use as a pre-commit or CI hook:
            agent = SecurityAgent()
            issues = agent.scan_diff(subprocess.check_output(["git", "diff", "--cached"]))

        Returns a list of Issue objects. Only lines beginning with '+' (but not
        '+++' header lines) are scanned.
        """
        issues = []
        current_file = "unknown"
        line_num = 0

        for raw_line in diff_text.splitlines():
            # Track which file we're in
            if raw_line.startswith("+++ "):
                # "+++ b/path/to/file"
                parts = raw_line[4:].strip()
                current_file = parts[2:] if parts.startswith("b/") else parts
                line_num = 0
                continue

            if raw_line.startswith("@@ "):
                # "@@ -a,b +c,d @@" — extract new-file start line
                m = re.search(r"\+(\d+)", raw_line)
                line_num = int(m.group(1)) - 1 if m else 0
                continue

            if raw_line.startswith("---"):
                continue

            if raw_line.startswith("+"):
                line_num += 1
                line = raw_line[1:]  # strip leading '+'
                for pattern, severity, message, suggestion, _ff, _ft in _ALL_PATTERNS:
                    if pattern.search(line):
                        issues.append(Issue(
                            source="security",
                            severity=severity,
                            file=current_file,
                            line=line_num,
                            message=f"[diff] {message}",
                            suggestion=suggestion,
                        ))
                        break  # one issue per added line
            elif not raw_line.startswith("-"):
                # context line — advance line counter for new file
                line_num += 1

        return issues
