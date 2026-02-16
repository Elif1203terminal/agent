"""Abstract base class for all specialist agents."""

import os
from abc import ABC, abstractmethod

from utils.llm import generate_code, parse_files


class BaseAgent(ABC):
    """Base class that every specialist agent must extend."""

    name = "base"
    description = "Base agent"
    category = "script"  # maps to CATEGORY_DIRS key
    system_prompt = ""  # each agent overrides with domain-specific prompt

    @abstractmethod
    def generate(self, request, output_dir):
        """Generate code files into output_dir based on the request.

        Returns a list of relative file paths that were created.
        """

    def _call_llm(self, request):
        """Send the request to Claude with this agent's system prompt."""
        return generate_code(self.system_prompt, request)

    def _parse_files(self, response):
        """Extract (filename, content) pairs from the LLM response."""
        return parse_files(response)

    def _generate_with_llm(self, request, output_dir):
        """Common pattern: call LLM, parse files, write to disk."""
        response = self._call_llm(request)
        files = self._parse_files(response)
        written = []
        for filepath, content in files:
            written.append(self.write_file(output_dir, filepath, content))
        return written

    def write_file(self, output_dir, relative_path, content):
        """Write content to a file inside output_dir, creating dirs as needed."""
        full_path = os.path.join(output_dir, relative_path)
        resolved = os.path.realpath(full_path)
        if not resolved.startswith(os.path.realpath(output_dir) + os.sep):
            raise ValueError(f"Path escapes output directory: {relative_path}")
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w") as f:
            f.write(content)
        return relative_path

    def plan(self, request):
        """Return a list of strings describing what files would be generated."""
        return [f"[{self.name}] Would generate files for: {request}"]
