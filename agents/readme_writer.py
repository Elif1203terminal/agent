"""README writer agent — generates beginner-friendly README.md for each project."""

import os

from utils.llm import call_llm
from core.state import PipelineState, FileEntry

_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "readme_writer.txt")


def _load_prompt():
    with open(_PROMPT_FILE) as f:
        return f.read()


class ReadmeWriter:
    """Generates a detailed README.md with setup and run instructions.

    Uses 1 LLM call. Runs AFTER the pipeline completes, not inside the loop.
    """

    name = "readme_writer"

    def run(self, state: PipelineState) -> PipelineState:
        if not state.current_files:
            return state

        prompt = _load_prompt()

        # Build context: stack, spec, file list, and key file contents
        parts = [
            f"PROJECT TYPE: {state.stack}",
            f"SPEC: {state.spec}",
            f"FILES IN PROJECT:",
        ]
        for f in state.current_files:
            parts.append(f"  - {f.path} ({f.language})")

        # Include requirements.txt content if it exists
        for f in state.current_files:
            if f.path == "requirements.txt":
                parts.append(f"\nREQUIREMENTS.TXT CONTENTS:\n{f.content}")
                break

        # Include the main entry point so the LLM knows how to run it
        for f in state.current_files:
            if f.path in ("app.py", "main.py"):
                # Just the first 30 lines to show imports and entry point
                lines = f.content.split("\n")[:30]
                parts.append(f"\nMAIN FILE ({f.path}) FIRST 30 LINES:\n" + "\n".join(lines))
                break

        user_message = "\n".join(parts)
        readme_content = call_llm(prompt, user_message)

        # Add README.md to the file list
        state.current_files.append(FileEntry(
            path="README.md",
            content=readme_content,
            language="markdown",
        ))

        return state
