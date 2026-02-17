"""Generator agent — produces or patches code files."""

import os

from utils.llm import call_llm, parse_files
from core.state import PipelineState, FileEntry

_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "generator.txt")


def _load_prompt():
    with open(_PROMPT_FILE) as f:
        return f.read()


def _guess_language(filepath):
    """Guess language from file extension."""
    ext_map = {
        ".py": "python", ".html": "html", ".css": "css",
        ".js": "javascript", ".json": "json", ".txt": "text",
        ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
        ".toml": "toml", ".cfg": "ini", ".ini": "ini",
    }
    _, ext = os.path.splitext(filepath)
    return ext_map.get(ext, "text")


class GeneratorAgent:
    """Generates code from spec, or patches existing code from instructions."""

    name = "generator"

    def run(self, state: PipelineState) -> PipelineState:
        state.status = "generating"
        prompt = _load_prompt()

        # Build user message
        parts = [
            f"Spec: {state.spec}",
            f"File manifest: {', '.join(state.file_manifest)}",
        ]

        # If patching (iteration > 0), include current files + patch instructions
        if state.current_files and state.patch_instructions:
            parts.append("\n--- CURRENT FILES (apply patches to these) ---")
            for f in state.current_files:
                parts.append(f"\n```{f.path}\n{f.content}\n```")
            parts.append(f"\n--- PATCH INSTRUCTIONS ---\n{state.patch_instructions}")

        user_message = "\n".join(parts)
        response = call_llm(prompt, user_message)
        parsed = parse_files(response)

        state.current_files = [
            FileEntry(path=path, content=content, language=_guess_language(path))
            for path, content in parsed
        ]

        # Clear patch instructions after applying
        state.patch_instructions = ""
        return state
