"""Security agent — static analysis, optional tool runners. Zero mandatory LLM calls."""

import json
import os
import re
import subprocess
import tempfile

from core.state import PipelineState, Issue
from config.rules import SECURITY_PATTERNS, HTML_SECURITY_PATTERNS

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
