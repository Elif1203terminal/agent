"""Pipeline state models shared across all stages."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileEntry:
    path: str           # relative path e.g. "app.py"
    content: str
    language: str       # "python", "html", "css", etc.


@dataclass
class Issue:
    source: str         # "reviewer", "tester", "security"
    severity: str       # "error", "warning", "info"
    file: str           # which file
    line: int | None
    message: str
    suggestion: str     # fix suggestion


@dataclass
class Iteration:
    number: int
    files: list[FileEntry]
    issues: list[Issue]
    lint_passed: bool
    tests_passed: bool
    security_passed: bool


@dataclass
class PipelineState:
    request: str
    category: str = ""
    stack: str = ""                     # "flask", "fastapi", etc.
    spec: str = ""                      # planner output
    file_manifest: list[str] = field(default_factory=list)
    iterations: list[Iteration] = field(default_factory=list)
    current_files: list[FileEntry] = field(default_factory=list)
    patch_instructions: str = ""        # from patch composer
    status: str = "planning"            # planning|generating|reviewing|testing|security|patching|awaiting_approval|done|failed
    max_iterations: int = 2
    output_dir: str = ""
    errors: list[str] = field(default_factory=list)
