"""Subprocess runner with command allowlist and timeout."""

import os
import subprocess

from config.defaults import DEFAULTS


def run_in_sandbox(command, cwd, timeout=None):
    """Run a command in a sandboxed subprocess.

    Args:
        command: Command as a list of strings, e.g. ["flake8", "app.py"]
        cwd: Working directory (must exist)
        timeout: Seconds before killing the process (default from config)

    Returns:
        (stdout, stderr, returncode) tuple

    Raises:
        ValueError: If command is not in the allowlist or cwd is invalid.
    """
    if timeout is None:
        timeout = DEFAULTS["sandbox_timeout"]

    if not command or not isinstance(command, list):
        raise ValueError("Command must be a non-empty list of strings")

    executable = command[0]
    allowed = DEFAULTS["allowed_commands"]
    if executable not in allowed:
        raise ValueError(
            f"Command '{executable}' not in allowlist: {allowed}"
        )

    cwd = os.path.realpath(cwd)
    if not os.path.isdir(cwd):
        raise ValueError(f"Working directory does not exist: {cwd}")

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {timeout}s", -1
    except FileNotFoundError:
        return "", f"Command not found: {executable}", -1
