"""Abstract base class for all specialist agents."""

import os
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Base class that every specialist agent must extend."""

    name = "base"
    description = "Base agent"
    category = "script"  # maps to CATEGORY_DIRS key

    @abstractmethod
    def generate(self, request, output_dir):
        """Generate code files into output_dir based on the request.

        Returns a list of relative file paths that were created.
        """

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
