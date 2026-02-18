"""Tester agent — runs lint and import checks in sandbox. Zero LLM calls."""

import os
import subprocess
import sys

from core.state import PipelineState, Issue
from core.sandbox import run_in_sandbox
from config.stacks import STACKS


def _create_venv(work_dir, timeout=120):
    """Create a temporary venv in work_dir and return the python path.

    Returns (python_path, pip_path) or (None, None) on failure.
    """
    venv_dir = os.path.join(work_dir, ".venv")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", venv_dir],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None

    if os.name == "nt":
        python = os.path.join(venv_dir, "Scripts", "python")
        pip = os.path.join(venv_dir, "Scripts", "pip")
    else:
        python = os.path.join(venv_dir, "bin", "python")
        pip = os.path.join(venv_dir, "bin", "pip")

    if not os.path.isfile(python):
        return None, None

    return python, pip


def _install_requirements(pip_path, work_dir, timeout=120):
    """Install requirements.txt using the venv pip. Returns (success, output)."""
    req_file = os.path.join(work_dir, "requirements.txt")
    if not os.path.isfile(req_file):
        return True, ""

    try:
        result = subprocess.run(
            [pip_path, "install", "-q", "-r", req_file],
            cwd=work_dir,
            capture_output=True, text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stderr[:500]
    except subprocess.TimeoutExpired:
        return False, "pip install timed out"
    except FileNotFoundError:
        return False, f"pip not found at {pip_path}"


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

        # Create a temp venv and install requirements before import check
        stack_config = STACKS.get(state.stack, {})
        test_cmd = stack_config.get("test_command", [])

        req_file = os.path.join(work_dir, "requirements.txt")
        has_requirements = os.path.isfile(req_file)
        venv_python = None

        if has_requirements and py_files:
            python_path, pip_path = _create_venv(work_dir)
            if python_path and pip_path:
                venv_python = python_path
                success, pip_output = _install_requirements(pip_path, work_dir)
                if not success:
                    issues.append(Issue(
                        source="tester",
                        severity="error",
                        file="requirements.txt",
                        line=None,
                        message=f"Failed to install dependencies: {pip_output[:200]}",
                        suggestion="Check that all packages in requirements.txt are valid and available on PyPI",
                    ))

        # Run import check using the venv python if available
        if test_cmd:
            if venv_python:
                # Replace "python3" with the venv python path
                run_cmd = [venv_python if c == "python3" else c for c in test_cmd]
            else:
                run_cmd = test_cmd

            try:
                result = subprocess.run(
                    run_cmd,
                    cwd=work_dir,
                    capture_output=True, text=True,
                    timeout=30,
                )
                stdout, stderr, rc = result.stdout, result.stderr, result.returncode
            except subprocess.TimeoutExpired:
                stdout, stderr, rc = "", "Import check timed out", -1
            except FileNotFoundError:
                stdout, stderr, rc = "", f"Command not found: {run_cmd[0]}", -1

            if rc != 0:
                error_text = stderr[:300]
                if "ModuleNotFoundError" in error_text:
                    severity = "warning"
                    suggestion = "Run: pip install -r requirements.txt"
                elif "SyntaxError" in error_text:
                    severity = "error"
                    suggestion = "Fix the syntax error in the generated code"
                else:
                    severity = "error"
                    suggestion = "Fix the import or runtime error"

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
