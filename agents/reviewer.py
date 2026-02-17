"""Reviewer agent — checks code for errors only. Strict scope, no style nits."""

import os

from utils.llm import call_llm
from core.state import PipelineState, Issue

_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "reviewer.txt")


def _load_prompt():
    with open(_PROMPT_FILE) as f:
        return f.read()


class ReviewerAgent:
    """Reviews generated code for functional errors only."""

    name = "reviewer"

    def run(self, state: PipelineState) -> PipelineState:
        state.status = "reviewing"

        if not state.current_files:
            return state

        prompt = _load_prompt()

        # Build context: all files
        parts = ["Review these files for errors:\n"]
        for f in state.current_files:
            parts.append(f"```{f.path}\n{f.content}\n```\n")

        user_message = "\n".join(parts)
        result = call_llm(prompt, user_message, response_format="json")

        issues = []
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    issues.append(Issue(
                        source="reviewer",
                        severity=item.get("severity", "warning"),
                        file=item.get("file", ""),
                        line=item.get("line"),
                        message=item.get("message", ""),
                        suggestion=item.get("suggestion", ""),
                    ))

        # Store issues on state for this stage
        state._review_issues = issues
        return state
