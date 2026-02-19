"""Tests for multi-platform DeployerAgent."""

import hashlib
import os
import re
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from agents.deployer import (
    BACKENDS,
    DeployerAgent,
    _FlyioBackend,
    _OracleSSHBackend,
    _RailwayBackend,
    _patch_requirements,
)
from core.state import FileEntry, PipelineState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(stack="flask", files=None, status="done", output_dir=""):
    state = PipelineState(request="test", stack=stack, status=status, output_dir=output_dir)
    state.current_files = files or []
    return state


def _py_file(path, content):
    return FileEntry(path=path, content=content, language="python")


# ---------------------------------------------------------------------------
# TestUnsupportedStack
# ---------------------------------------------------------------------------

class TestUnsupportedStack:
    def test_cli_stack_unsupported(self):
        state = _make_state(stack="cli")
        result = DeployerAgent().run(state, "/tmp/fake")
        assert result["url"] is None
        assert "cli" in result["error"].lower()
        assert result["issues"] == []

    def test_data_stack_unsupported(self):
        state = _make_state(stack="data")
        result = DeployerAgent().run(state, "/tmp/fake")
        assert result["url"] is None
        assert result["error"] is not None
        assert result["issues"] == []


# ---------------------------------------------------------------------------
# TestUnknownPlatform
# ---------------------------------------------------------------------------

class TestUnknownPlatform:
    def test_bogus_platform_error(self):
        state = _make_state(stack="flask")
        result = DeployerAgent().run(state, "/tmp/fake", platform="heroku")
        assert result["url"] is None
        assert "heroku" in result["error"]
        assert "fly" in result["error"] or "Valid" in result["error"]


# ---------------------------------------------------------------------------
# TestRailwayBackendConfig
# ---------------------------------------------------------------------------

class TestRailwayBackendConfig:
    def test_flask_procfile(self, tmp_path):
        _RailwayBackend().write_config(str(tmp_path), "flask")
        content = (tmp_path / "Procfile").read_text()
        assert "gunicorn" in content
        assert "$PORT" in content

    def test_fastapi_procfile(self, tmp_path):
        _RailwayBackend().write_config(str(tmp_path), "fastapi")
        content = (tmp_path / "Procfile").read_text()
        assert "uvicorn" in content
        assert "$PORT" in content


# ---------------------------------------------------------------------------
# TestFlyioBackendConfig
# ---------------------------------------------------------------------------

class TestFlyioBackendConfig:
    def test_dockerfile_flask_cmd(self, tmp_path):
        _FlyioBackend().write_config(str(tmp_path), "flask")
        content = (tmp_path / "Dockerfile").read_text()
        assert "gunicorn" in content
        assert "8080" in content

    def test_dockerfile_fastapi_cmd(self, tmp_path):
        _FlyioBackend().write_config(str(tmp_path), "fastapi")
        content = (tmp_path / "Dockerfile").read_text()
        assert "uvicorn" in content
        assert "8080" in content

    def test_fly_toml_written(self, tmp_path):
        _FlyioBackend().write_config(str(tmp_path), "flask")
        assert (tmp_path / "fly.toml").exists()
        content = (tmp_path / "fly.toml").read_text()
        assert "internal_port = 8080" in content

    def test_app_name_slug_and_hash(self, tmp_path):
        _FlyioBackend().write_config(str(tmp_path), "flask")
        content = (tmp_path / "fly.toml").read_text()
        work_dir = str(tmp_path)
        dirname = os.path.basename(work_dir).lower()
        slug = re.sub(r"[^a-z0-9-]", "-", dirname)[:20].strip("-") or "app"
        hash_suffix = hashlib.md5(work_dir.encode()).hexdigest()[:6]
        expected_name = f"{slug}-{hash_suffix}"
        assert expected_name in content


# ---------------------------------------------------------------------------
# TestRequirementsPatch
# ---------------------------------------------------------------------------

class TestRequirementsPatch:
    def test_gunicorn_added(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        _patch_requirements(str(tmp_path), "gunicorn")
        assert "gunicorn" in (tmp_path / "requirements.txt").read_text()

    def test_uvicorn_added(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        _patch_requirements(str(tmp_path), "uvicorn")
        assert "uvicorn" in (tmp_path / "requirements.txt").read_text()

    def test_no_duplicate(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask\ngunicorn\n")
        _patch_requirements(str(tmp_path), "gunicorn")
        content = (tmp_path / "requirements.txt").read_text()
        assert content.count("gunicorn") == 1


# ---------------------------------------------------------------------------
# TestCorsWarning
# ---------------------------------------------------------------------------

class TestCorsWarning:
    def test_wildcard_produces_warning(self):
        files = [_py_file("app.py", "allow_origins=['*']\n")]
        state = _make_state(files=files)
        issues = DeployerAgent()._check_cors(state)
        assert len(issues) >= 1
        assert all(i.severity == "warning" for i in issues)
        assert all(i.source == "deployer" for i in issues)

    def test_safe_cors_no_issues(self):
        files = [_py_file("app.py", "allow_origins=['https://example.com']\n")]
        state = _make_state(files=files)
        issues = DeployerAgent()._check_cors(state)
        assert issues == []


# ---------------------------------------------------------------------------
# TestCliMissing
# ---------------------------------------------------------------------------

class TestCliMissing:
    def test_railway_cli_absent(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        with patch("shutil.which", return_value=None), \
             patch.dict(os.environ, {"RAILWAY_TOKEN": "tok"}):
            result = DeployerAgent().run(state, str(tmp_path), platform="railway")
        assert result["url"] is None
        assert result["error"] is not None

    def test_flyctl_and_fly_both_absent(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        with patch("shutil.which", return_value=None), \
             patch.dict(os.environ, {"FLY_API_TOKEN": "tok"}):
            result = DeployerAgent().run(state, str(tmp_path), platform="fly")
        assert result["url"] is None
        assert result["error"] is not None


# ---------------------------------------------------------------------------
# TestAuthMissing
# ---------------------------------------------------------------------------

class TestAuthMissing:
    def test_railway_token_absent(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        with patch("shutil.which", return_value="/usr/bin/railway"), \
             patch.dict(os.environ, {}, clear=True):
            result = DeployerAgent().run(state, str(tmp_path), platform="railway")
        assert result["url"] is None
        assert "RAILWAY_TOKEN" in result["error"]

    def test_oci_host_absent(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        with patch("shutil.which", return_value="/usr/bin/ssh"), \
             patch.dict(os.environ, {}, clear=True):
            result = DeployerAgent().run(state, str(tmp_path), platform="oracle")
        assert result["url"] is None
        assert "OCI_HOST" in result["error"]


# ---------------------------------------------------------------------------
# TestCliDeploy
# ---------------------------------------------------------------------------

class TestCliDeploy:
    def test_success_extracts_url(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        mock_result = MagicMock(
            returncode=0,
            stdout="Live at https://myapp.railway.app",
            stderr="",
        )
        with patch("shutil.which", return_value="/usr/bin/railway"), \
             patch("subprocess.run", return_value=mock_result), \
             patch.dict(os.environ, {"RAILWAY_TOKEN": "tok"}):
            result = DeployerAgent().run(state, str(tmp_path), platform="railway")
        assert result["url"] == "https://myapp.railway.app"
        assert result["error"] is None

    def test_nonzero_exit_returns_error(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        mock_result = MagicMock(returncode=1, stdout="", stderr="Auth failed")
        with patch("shutil.which", return_value="/usr/bin/railway"), \
             patch("subprocess.run", return_value=mock_result), \
             patch.dict(os.environ, {"RAILWAY_TOKEN": "tok"}):
            result = DeployerAgent().run(state, str(tmp_path), platform="railway")
        assert result["url"] is None
        assert "exit 1" in result["error"] or "failed" in result["error"].lower()

    def test_timeout_returns_error(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        with patch("shutil.which", return_value="/usr/bin/railway"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("railway", 120)), \
             patch.dict(os.environ, {"RAILWAY_TOKEN": "tok"}):
            result = DeployerAgent().run(state, str(tmp_path), platform="railway")
        assert result["url"] is None
        assert "timed out" in result["error"].lower()


# ---------------------------------------------------------------------------
# TestOracleSSHDeploy
# ---------------------------------------------------------------------------

class TestOracleSSHDeploy:
    def _env(self):
        return {"OCI_HOST": "1.2.3.4", "OCI_SSH_KEY": "/tmp/key.pem"}

    def test_rsync_failure(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        rsync_fail = MagicMock(returncode=1, stdout="", stderr="Connection refused")
        with patch("shutil.which", return_value="/usr/bin/ssh"), \
             patch("subprocess.run", return_value=rsync_fail), \
             patch.dict(os.environ, self._env()):
            result = DeployerAgent().run(state, str(tmp_path), platform="oracle")
        assert result["url"] is None
        assert "rsync" in result["error"].lower()

    def test_ssh_failure(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        rsync_ok = MagicMock(returncode=0, stdout="", stderr="")
        ssh_fail = MagicMock(returncode=1, stdout="", stderr="Permission denied")
        with patch("shutil.which", return_value="/usr/bin/ssh"), \
             patch("subprocess.run", side_effect=[rsync_ok, ssh_fail]), \
             patch.dict(os.environ, self._env()):
            result = DeployerAgent().run(state, str(tmp_path), platform="oracle")
        assert result["url"] is None
        assert "SSH" in result["error"] or "failed" in result["error"].lower()

    def test_success_returns_url(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        rsync_ok = MagicMock(returncode=0, stdout="", stderr="")
        ssh_ok = MagicMock(returncode=0, stdout="", stderr="")
        with patch("shutil.which", return_value="/usr/bin/ssh"), \
             patch("subprocess.run", side_effect=[rsync_ok, ssh_ok]), \
             patch.dict(os.environ, self._env()):
            result = DeployerAgent().run(state, str(tmp_path), platform="oracle")
        assert result["url"] == "http://1.2.3.4:8000"
        assert result["error"] is None


# ---------------------------------------------------------------------------
# TestIdempotent
# ---------------------------------------------------------------------------

class TestIdempotent:
    def test_procfile_preserved(self, tmp_path):
        original = "web: python run.py\n"
        (tmp_path / "Procfile").write_text(original)
        _RailwayBackend().write_config(str(tmp_path), "flask")
        assert (tmp_path / "Procfile").read_text() == original

    def test_dockerfile_preserved(self, tmp_path):
        original = "FROM alpine\n"
        (tmp_path / "Dockerfile").write_text(original)
        _FlyioBackend().write_config(str(tmp_path), "flask")
        assert (tmp_path / "Dockerfile").read_text() == original

    def test_fly_toml_preserved(self, tmp_path):
        original = 'app = "my-existing-app"\n'
        (tmp_path / "fly.toml").write_text(original)
        _FlyioBackend().write_config(str(tmp_path), "flask")
        assert (tmp_path / "fly.toml").read_text() == original


# ---------------------------------------------------------------------------
# TestRequirementsCreated
# ---------------------------------------------------------------------------

class TestRequirementsCreated:
    def test_created_from_scratch(self, tmp_path):
        _patch_requirements(str(tmp_path), "uvicorn")
        req_path = tmp_path / "requirements.txt"
        assert req_path.exists()
        assert "uvicorn" in req_path.read_text()


# ---------------------------------------------------------------------------
# TestApiDeployEndpoint
# ---------------------------------------------------------------------------

class TestApiDeployEndpoint:
    @pytest.fixture(autouse=True)
    def client(self):
        import server
        server.app.config["TESTING"] = True
        self.server = server
        self.client = server.app.test_client()

    def test_404_unknown_job(self):
        res = self.client.post("/api/deploy",
                               json={"job_id": "nonexistent"},
                               content_type="application/json")
        assert res.status_code == 404
        assert "not found" in res.get_json()["error"].lower()

    def test_400_unapproved_job(self):
        state = _make_state(stack="flask", status="awaiting_approval")
        job_id = self.server._store_job(state)
        res = self.client.post("/api/deploy",
                               json={"job_id": job_id},
                               content_type="application/json")
        assert res.status_code == 400
        data = res.get_json()
        assert "approved" in data["error"].lower() or "done" in data["error"].lower()

    def test_200_with_platform_and_url(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        job_id = self.server._store_job(state)
        mock_result = MagicMock(
            returncode=0,
            stdout="Live at https://myapp.fly.dev",
            stderr="",
        )
        with patch("shutil.which", return_value="/usr/bin/flyctl"), \
             patch("subprocess.run", return_value=mock_result), \
             patch.dict(os.environ, {"FLY_API_TOKEN": "tok"}):
            res = self.client.post("/api/deploy",
                                   json={"job_id": job_id, "platform": "fly"},
                                   content_type="application/json")
        assert res.status_code == 200
        data = res.get_json()
        assert data["deploy_url"] == "https://myapp.fly.dev"
        assert data["platform"] == "fly"
        assert data["deploy_error"] is None

    def test_200_with_deploy_error(self, tmp_path):
        state = _make_state(stack="flask", status="done", output_dir=str(tmp_path))
        job_id = self.server._store_job(state)
        with patch("shutil.which", return_value=None), \
             patch.dict(os.environ, {"RAILWAY_TOKEN": "tok"}):
            res = self.client.post("/api/deploy",
                                   json={"job_id": job_id, "platform": "railway"},
                                   content_type="application/json")
        assert res.status_code == 200
        data = res.get_json()
        assert data["deploy_url"] is None
        assert data["deploy_error"] is not None


# ---------------------------------------------------------------------------
# TestUrlRegex
# ---------------------------------------------------------------------------

class TestUrlRegex:
    def test_fly_dev_regex(self):
        backend = _FlyioBackend()
        text = "App deployed to https://my-cool-app.fly.dev — enjoy!"
        url = backend.extract_url(text, "")
        assert url == "https://my-cool-app.fly.dev"

    def test_railway_app_regex(self):
        backend = _RailwayBackend()
        text = "Live at https://cool-app-123.railway.app"
        url = backend.extract_url(text, "")
        assert url == "https://cool-app-123.railway.app"


# ---------------------------------------------------------------------------
# TestFlyioCLIFallback
# ---------------------------------------------------------------------------

class TestFlyioCLIFallback:
    def test_flyctl_absent_fly_present(self):
        backend = _FlyioBackend()
        with patch("shutil.which", side_effect=lambda x: "/usr/bin/fly" if x == "fly" else None):
            cli = backend.find_cli()
        assert cli == "fly"
