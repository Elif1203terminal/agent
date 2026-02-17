"""Tester agent — runs lint and import checks in sandbox. Zero LLM calls."""

import os

from core.state import PipelineState, Issue
from core.sandbox import run_in_sandbox
from config.stacks import STACKS


class TesterAgent:
    """Runs flake8 and import checks. No LLM calls — pure subprocess."""

    name = "tester"

    def run(self, state: PipelineState, work_dir: str) -> PipelineState:
        state.status = "testing"
        issues = []
        lint_passed = True

        if not os.path.isdir(work_dir):
            state._test_issues = []
            state._lint_passed = True
            state._tests_passed = True
            return state

        # Write current files to work_dir for testing
        for f in state.current_files:
            fpath = os.path.join(work_dir, f.path)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w") as fp:
                fp.write(f.content)

        # Find Python files to lint
        py_files = [f.path for f in state.current_files if f.path.endswith(".py")]

        # Run flake8 on each Python file
        for py_file in py_files:
            stdout, stderr, rc = run_in_sandbox(
                ["flake8", "--max-line-length=120", py_file],
                cwd=work_dir,
            )
            if rc != 0 and stdout.strip():
                lint_passed = False
                for line in stdout.strip().split("\n"):
                    # flake8 format: file.py:line:col: CODE message
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        issues.append(Issue(
                            source="tester",
                            severity="warning",
                            file=parts[0].strip(),
                            line=int(parts[1]) if parts[1].strip().isdigit() else None,
                            message=parts[3].strip() if len(parts) > 3 else parts[2].strip(),
                            suggestion="Fix the linting error",
                        ))

        # Install requirements if present, then run import check
        stack_config = STACKS.get(state.stack, {})
        test_cmd = stack_config.get("test_command", [])

        req_file = os.path.join(work_dir, "requirements.txt")
        if test_cmd and os.path.isfile(req_file):
            run_in_sandbox(["pip", "install", "-q", "-r", "requirements.txt"],
                           cwd=work_dir, timeout=60)

        if test_cmd:
            stdout, stderr, rc = run_in_sandbox(test_cmd, cwd=work_dir)
            if rc != 0:
                error_text = stderr[:300]
                # Missing third-party modules are a warning, not an error —
                # the generated project includes requirements.txt for the user
                if "ModuleNotFoundError" in error_text:
                    severity = "warning"
                    suggestion = "Run: pip install -r requirements.txt"
                else:
                    severity = "error"
                    suggestion = "Fix the import or syntax error"

                import_arg = test_cmd[-1] if test_cmd else ""
                module = import_arg.replace("import ", "") if import_arg.startswith("import ") else import_arg
                issues.append(Issue(
                    source="tester",
                    severity=severity,
                    file=f"{module}.py",
                    line=None,
                    message=f"Import check: {error_text}",
                    suggestion=suggestion,
                ))

        state._test_issues = issues
        state._lint_passed = lint_passed
        state._tests_passed = not any(i.severity == "error" for i in issues)
        return state
