"""Planner agent — breaks a request into spec + file manifest."""

import os

from utils.llm import call_llm
from core.state import PipelineState
from config.stacks import CATEGORY_TO_STACK

_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "planner.txt")


def _load_prompt():
    with open(_PROMPT_FILE) as f:
        return f.read()


class PlannerAgent:
    """Produces a spec and file manifest from a user request."""

    name = "planner"

    def run(self, state: PipelineState) -> PipelineState:
        state.status = "planning"
        prompt = _load_prompt()

        user_message = (
            f"Category: {state.category}\n"
            f"Request: {state.request}"
        )

        result = call_llm(prompt, user_message, response_format="json")

        if isinstance(result, dict):
            state.spec = result.get("spec", "")
            state.file_manifest = result.get("file_manifest", [])
            state.stack = result.get("stack", CATEGORY_TO_STACK.get(state.category, "script"))
        else:
            # Fallback if JSON parsing failed — treat as spec text
            state.spec = str(result)
            state.stack = CATEGORY_TO_STACK.get(state.category, "script")

        return state
