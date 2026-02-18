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

        is_patching = bool(state.current_files and state.patch_instructions)

        if is_patching:
            # PATCH MODE: only send files that have errors
            broken_files = self._get_broken_files(state)

            parts = [
                f"Spec: {state.spec}",
                f"\n--- FILES TO FIX (output ONLY these files, complete) ---",
            ]
            for f in broken_files:
                parts.append(f"\n```{f.path}\n{f.content}\n```")
            parts.append(f"\n--- PATCH INSTRUCTIONS ---\n{state.patch_instructions}")

            user_message = "\n".join(parts)
            response = call_llm(prompt, user_message)
            parsed = parse_files(response)

            # Merge: replace patched files, keep unchanged files as-is
            patched_paths = {path for path, _ in parsed}
            new_files = []

            # Keep unchanged files
            for f in state.current_files:
                if f.path not in patched_paths:
                    new_files.append(f)

            # Add patched files
            for path, content in parsed:
                new_files.append(
                    FileEntry(path=path, content=content, language=_guess_language(path))
                )

            state.current_files = new_files
        else:
            # FIRST GENERATION: produce all files
            parts = [
                f"Spec: {state.spec}",
                f"File manifest: {', '.join(state.file_manifest)}",
            ]

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

    def _get_broken_files(self, state):
        """Extract the set of files that have issues from the last iteration."""
        broken_paths = set()

        if state.iterations:
            last_iter = state.iterations[-1]
            for issue in last_iter.issues:
                if issue.severity == "error" and issue.file:
                    # Map the issue file to an actual file in current_files
                    for f in state.current_files:
                        if issue.file in f.path or f.path.endswith(issue.file):
                            broken_paths.add(f.path)
                            break

        # If we couldn't identify specific files, send all of them
        if not broken_paths:
            return list(state.current_files)

        return [f for f in state.current_files if f.path in broken_paths]
