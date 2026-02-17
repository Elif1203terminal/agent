"""Tests for core.sandbox."""

import os
import tempfile
import pytest

from core.sandbox import run_in_sandbox


def test_allowed_command():
    with tempfile.TemporaryDirectory() as tmpdir:
        stdout, stderr, rc = run_in_sandbox(["python3", "--version"], cwd=tmpdir)
        assert rc == 0
        assert "Python" in stdout or "Python" in stderr


def test_disallowed_command():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="not in allowlist"):
            run_in_sandbox(["rm", "-rf", "/"], cwd=tmpdir)


def test_disallowed_curl():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="not in allowlist"):
            run_in_sandbox(["curl", "http://example.com"], cwd=tmpdir)


def test_disallowed_bash():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="not in allowlist"):
            run_in_sandbox(["bash", "-c", "echo pwned"], cwd=tmpdir)


def test_invalid_cwd():
    with pytest.raises(ValueError, match="does not exist"):
        run_in_sandbox(["python3", "--version"], cwd="/nonexistent/path")


def test_empty_command():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="non-empty list"):
            run_in_sandbox([], cwd=tmpdir)


def test_timeout():
    with tempfile.TemporaryDirectory() as tmpdir:
        stdout, stderr, rc = run_in_sandbox(
            ["python3", "-c", "import time; time.sleep(10)"],
            cwd=tmpdir,
            timeout=1,
        )
        assert rc == -1
        assert "timed out" in stderr.lower()


def test_command_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Add a fake command to allowlist temporarily
        from config.defaults import DEFAULTS
        orig = DEFAULTS["allowed_commands"][:]
        DEFAULTS["allowed_commands"].append("nonexistent_cmd_xyz")
        try:
            stdout, stderr, rc = run_in_sandbox(
                ["nonexistent_cmd_xyz"], cwd=tmpdir
            )
            assert rc == -1
            assert "not found" in stderr.lower()
        finally:
            DEFAULTS["allowed_commands"] = orig
