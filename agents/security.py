"""Security agent — regex pattern matching + auto-fix. Zero LLM calls."""

from core.state import PipelineState, Issue
from config.rules import SECURITY_PATTERNS


class SecurityAgent:
    """Scans code for security issues and auto-fixes trivial ones. No LLM calls."""

    name = "security"

    def run(self, state: PipelineState) -> PipelineState:
        state.status = "security"
        issues = []
        fixes_applied = 0

        for f in state.current_files:
            if not f.path.endswith(".py"):
                continue

            # First pass: auto-fix what we can
            content = f.content
            for pattern, severity, message, suggestion, fix_from, fix_to in SECURITY_PATTERNS:
                if fix_from and fix_to and fix_from.search(content):
                    content = fix_from.sub(fix_to, content)
                    fixes_applied += 1

            # Apply fixes to the file
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

        if fixes_applied:
            state._security_fixes_applied = fixes_applied

        state._security_issues = issues
        return state
