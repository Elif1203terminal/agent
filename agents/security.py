"""Security agent — regex pattern matching only. Zero LLM calls."""

from core.state import PipelineState, Issue
from config.rules import SECURITY_PATTERNS


class SecurityAgent:
    """Scans code for security issues using regex patterns. No LLM calls."""

    name = "security"

    def run(self, state: PipelineState) -> PipelineState:
        state.status = "security"
        issues = []

        for f in state.current_files:
            if not f.path.endswith(".py"):
                continue

            lines = f.content.split("\n")
            for line_num, line in enumerate(lines, 1):
                for pattern, severity, message, suggestion in SECURITY_PATTERNS:
                    if pattern.search(line):
                        issues.append(Issue(
                            source="security",
                            severity=severity,
                            file=f.path,
                            line=line_num,
                            message=message,
                            suggestion=suggestion,
                        ))

        state._security_issues = issues
        return state
