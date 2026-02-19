"""Security agent — regex pattern matching + auto-fix. Zero LLM calls."""

import re

from core.state import PipelineState, Issue
from config.rules import SECURITY_PATTERNS, HTML_SECURITY_PATTERNS

_TEMPLATE_EXTENSIONS = {".html", ".jinja2", ".j2"}


class SecurityAgent:
    """Scans code for security issues and auto-fixes trivial ones. No LLM calls."""

    name = "security"

    def run(self, state: PipelineState) -> PipelineState:
        state.status = "security"
        issues = []
        fixes_applied = 0

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

                # Whole-file CSRF check: POST form without any csrf token
                csrf_issue = self._check_csrf(f)
                if csrf_issue:
                    issues.append(csrf_issue)

        if fixes_applied:
            state._security_fixes_applied = fixes_applied

        state._security_issues = issues
        return state

    def _check_csrf(self, f) -> Issue | None:
        """Flag a template that has a POST form but no CSRF token anywhere in the file."""
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
