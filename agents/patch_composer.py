"""Patch composer — aggregates issues into patch instructions. Zero LLM calls."""

from core.state import PipelineState


class PatchComposer:
    """Collects issues from all agents and formats patch instructions."""

    name = "patch_composer"

    def run(self, state: PipelineState, all_issues) -> PipelineState:
        # Don't override status — orchestrator manages it

        if not all_issues:
            state.patch_instructions = ""
            return state

        # Only include errors and warnings — skip info
        actionable = [i for i in all_issues if i.severity in ("error", "warning")]

        if not actionable:
            state.patch_instructions = ""
            return state

        # Sort: errors first, then by file
        actionable.sort(key=lambda i: (0 if i.severity == "error" else 1, i.file))

        lines = ["Fix the following issues in the code:\n"]
        for idx, issue in enumerate(actionable, 1):
            loc = f"{issue.file}"
            if issue.line:
                loc += f" line {issue.line}"
            lines.append(
                f"{idx}. [{issue.severity.upper()}] {loc}: {issue.message}\n"
                f"   Fix: {issue.suggestion}"
            )

        state.patch_instructions = "\n".join(lines)
        return state
