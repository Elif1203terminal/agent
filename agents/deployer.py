"""DeployerAgent — packages and pushes generated apps to Fly.io, Oracle Cloud SSH, or Railway."""

import hashlib
import os
import re
import shutil
import subprocess

from core.state import Issue
from config.rules import SECURITY_PATTERNS

_CORS_PATTERNS = [e for e in SECURITY_PATTERNS if "CORS" in e[2]]


def _patch_requirements(work_dir: str, package: str) -> None:
    """Ensure *package* appears in requirements.txt (creates the file if missing)."""
    req_path = os.path.join(work_dir, "requirements.txt")
    existing_lines = []
    if os.path.exists(req_path):
        with open(req_path) as f:
            existing_lines = f.read().splitlines()

    bare_names = set()
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        bare = re.split(r"[><=!\[;]", stripped)[0].strip().lower()
        bare_names.add(bare)

    if package not in bare_names:
        existing_lines.append(package)
        with open(req_path, "w") as f:
            f.write("\n".join(existing_lines) + "\n")


class _RailwayBackend:
    name = "railway"
    label = "Railway"
    cli_names = ["railway"]
    install_hint = "npm install -g @railway/cli"
    url_re = re.compile(r"https://\S+\.railway\.app")
    env_var = "RAILWAY_TOKEN"
    env_hint = "export RAILWAY_TOKEN=<token from railway.app/account/tokens>"

    def write_config(self, work_dir: str, stack: str) -> None:
        """Write Procfile if one does not already exist (idempotent)."""
        procfile_path = os.path.join(work_dir, "Procfile")
        if os.path.exists(procfile_path):
            return
        if stack == "flask":
            content = "web: gunicorn app:app --bind 0.0.0.0:$PORT\n"
        else:
            content = "web: uvicorn app:app --host 0.0.0.0 --port $PORT\n"
        with open(procfile_path, "w") as f:
            f.write(content)

    def patch_requirements(self, work_dir: str, stack: str) -> None:
        _patch_requirements(work_dir, "gunicorn" if stack == "flask" else "uvicorn")

    def deploy_args(self):
        return ["up"]

    def find_cli(self):
        for name in self.cli_names:
            if shutil.which(name):
                return name
        return None

    def auth_ok(self):
        return bool(os.environ.get(self.env_var))

    def extract_url(self, stdout: str, stderr: str):
        combined = stdout + stderr
        match = self.url_re.search(combined)
        return match.group(0) if match else None


class _FlyioBackend:
    name = "fly"
    label = "Fly.io (free)"
    cli_names = ["flyctl", "fly"]
    install_hint = "curl -L https://fly.io/install.sh | sh  then: fly auth login"
    url_re = re.compile(r"https://\S+\.fly\.dev")
    env_var = "FLY_API_TOKEN"
    env_hint = "Run `fly auth login` or: export FLY_API_TOKEN=$(fly auth token)"

    def write_config(self, work_dir: str, stack: str) -> None:
        self._write_dockerfile(work_dir, stack)
        self._write_fly_toml(work_dir)

    def _write_dockerfile(self, work_dir: str, stack: str) -> None:
        path = os.path.join(work_dir, "Dockerfile")
        if os.path.exists(path):
            return
        if stack == "flask":
            cmd = '["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2"]'
        else:
            cmd = '["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]'
        content = (
            "FROM python:3.11-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt .\n"
            "RUN pip install --no-cache-dir -r requirements.txt\n"
            "COPY . .\n"
            "EXPOSE 8080\n"
            f"CMD {cmd}\n"
        )
        with open(path, "w") as f:
            f.write(content)

    def _write_fly_toml(self, work_dir: str) -> None:
        path = os.path.join(work_dir, "fly.toml")
        if os.path.exists(path):
            return
        dirname = os.path.basename(work_dir).lower()
        slug = re.sub(r"[^a-z0-9-]", "-", dirname)[:20].strip("-") or "app"
        hash_suffix = hashlib.md5(work_dir.encode()).hexdigest()[:6]
        app_name = f"{slug}-{hash_suffix}"
        content = (
            f'app = "{app_name}"\n'
            'primary_region = "iad"\n'
            "\n"
            "[http_service]\n"
            "  internal_port = 8080\n"
            "  force_https = true\n"
            "  auto_stop_machines = true\n"
            "  min_machines_running = 0\n"
            "\n"
            "[[vm]]\n"
            '  memory = "256mb"\n'
            '  cpu_kind = "shared"\n'
            "  cpus = 1\n"
        )
        with open(path, "w") as f:
            f.write(content)

    def patch_requirements(self, work_dir: str, stack: str) -> None:
        _patch_requirements(work_dir, "gunicorn" if stack == "flask" else "uvicorn")

    def deploy_args(self):
        return ["deploy", "--remote-only", "--yes"]

    def find_cli(self):
        for name in self.cli_names:
            if shutil.which(name):
                return name
        return None

    def auth_ok(self):
        return bool(os.environ.get(self.env_var))

    def extract_url(self, stdout: str, stderr: str):
        combined = stdout + stderr
        match = self.url_re.search(combined)
        return match.group(0) if match else None


class _OracleSSHBackend:
    name = "oracle"
    label = "Oracle Cloud (free)"
    cli_names = ["ssh"]
    install_hint = "ssh and rsync must be installed (standard on Linux/macOS)"
    url_re = None
    env_var = "OCI_HOST"
    env_hint = (
        "Set OCI_HOST=<public-ip>, OCI_SSH_KEY=<path/to/key.pem>. "
        "Optional: OCI_USER (default: ubuntu), OCI_APP_PORT (default: 8000)"
    )

    def write_config(self, work_dir: str, stack: str) -> None:
        pass  # no platform config file needed

    def patch_requirements(self, work_dir: str, stack: str) -> None:
        _patch_requirements(work_dir, "gunicorn" if stack == "flask" else "uvicorn")

    def find_cli(self):
        return "ssh" if (shutil.which("ssh") and shutil.which("rsync")) else None

    def auth_ok(self):
        return bool(os.environ.get("OCI_HOST") and os.environ.get("OCI_SSH_KEY"))

    def custom_deploy(self, work_dir: str, stack: str) -> tuple:
        host = os.environ["OCI_HOST"]
        key = os.environ["OCI_SSH_KEY"]
        user = os.environ.get("OCI_USER", "ubuntu")
        port = os.environ.get("OCI_APP_PORT", "8000")
        remote_dir = f"/home/{user}/app"
        ssh_opts = ["-i", key, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes"]

        rsync_cmd = [
            "rsync", "-avz",
            "--exclude=.venv", "--exclude=__pycache__", "--exclude=*.pyc",
            "-e", "ssh " + " ".join(ssh_opts),
            f"{work_dir}/", f"{user}@{host}:{remote_dir}/",
        ]
        try:
            rsync_result = subprocess.run(
                rsync_cmd, capture_output=True, text=True, timeout=60
            )
        except subprocess.TimeoutExpired:
            return (None, "rsync timed out after 60 seconds")
        except FileNotFoundError:
            return (None, "rsync not found")

        if rsync_result.returncode != 0:
            detail = (rsync_result.stderr or rsync_result.stdout or "no output").strip()
            return (None, f"rsync failed (exit {rsync_result.returncode}): {detail}")

        if stack == "flask":
            server_cmd = (
                f"nohup .venv/bin/gunicorn app:app --bind 0.0.0.0:{port} "
                "--workers 2 > app.log 2>&1 & echo $! > .app.pid"
            )
        else:
            server_cmd = (
                f"nohup .venv/bin/uvicorn app:app --host 0.0.0.0 --port {port} "
                "> app.log 2>&1 & echo $! > .app.pid"
            )

        script = (
            "set -e\n"
            f"cd {remote_dir}\n"
            "if [ -f .app.pid ] && kill -0 $(cat .app.pid) 2>/dev/null; then\n"
            "    kill $(cat .app.pid); sleep 1; fi\n"
            "python3 -m venv .venv 2>/dev/null || true\n"
            ".venv/bin/pip install -q -r requirements.txt\n"
            f"{server_cmd}\n"
        )

        ssh_cmd = ["ssh"] + ssh_opts + [f"{user}@{host}", "bash -s"]
        try:
            ssh_result = subprocess.run(
                ssh_cmd, input=script, capture_output=True, text=True, timeout=120
            )
        except subprocess.TimeoutExpired:
            return (None, "SSH deploy timed out after 120 seconds")
        except FileNotFoundError:
            return (None, "ssh not found")

        if ssh_result.returncode != 0:
            detail = (ssh_result.stderr or ssh_result.stdout or "no output").strip()
            return (None, f"SSH deploy failed (exit {ssh_result.returncode}): {detail}")

        return (f"http://{host}:{port}", None)


BACKENDS = {
    "fly": _FlyioBackend(),
    "oracle": _OracleSSHBackend(),
    "railway": _RailwayBackend(),
}


class DeployerAgent:
    SUPPORTED_STACKS = {"flask", "fastapi"}
    BACKENDS = BACKENDS

    def run(self, state, work_dir: str, platform: str = "fly") -> dict:
        """Deploy to the specified platform. Returns {"url", "issues", "error"}."""
        if state.stack not in self.SUPPORTED_STACKS:
            return {
                "url": None,
                "issues": [],
                "error": f"Stack '{state.stack}' is not supported for deployment.",
            }

        backend = BACKENDS.get(platform)
        if backend is None:
            valid = ", ".join(sorted(BACKENDS.keys()))
            return {
                "url": None,
                "issues": [],
                "error": f"Unknown platform '{platform}'. Valid options: {valid}",
            }

        cors_issues = self._check_cors(state)
        backend.write_config(work_dir, state.stack)
        backend.patch_requirements(work_dir, state.stack)

        if backend.find_cli() is None:
            return {
                "url": None,
                "issues": cors_issues,
                "error": f"{backend.label} CLI not found. {backend.install_hint}",
            }

        if not backend.auth_ok():
            return {
                "url": None,
                "issues": cors_issues,
                "error": f"{backend.env_var} not set. {backend.env_hint}",
            }

        if hasattr(backend, "custom_deploy"):
            url, error = backend.custom_deploy(work_dir, state.stack)
        else:
            url, error = self._run_cli_deploy(backend, work_dir)

        return {"url": url, "issues": cors_issues, "error": error}

    def _check_cors(self, state) -> list:
        """Scan .py files in current_files for CORS wildcard patterns. Warn-only."""
        issues = []
        for file_entry in state.current_files:
            if not file_entry.path.endswith(".py"):
                continue
            for pattern, severity, message, suggestion, _, _ in _CORS_PATTERNS:
                for lineno, line in enumerate(file_entry.content.splitlines(), 1):
                    if pattern.search(line):
                        issues.append(Issue(
                            source="deployer",
                            severity="warning",
                            file=file_entry.path,
                            line=lineno,
                            message=message,
                            suggestion=suggestion,
                        ))
        return issues

    def _run_cli_deploy(self, backend, work_dir: str) -> tuple:
        """Run the backend CLI deploy command. Returns (url|None, error|None)."""
        cli = backend.find_cli()
        cmd = [cli] + backend.deploy_args()
        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return (None, "Deploy timed out after 120 seconds")
        except FileNotFoundError:
            return (None, f"CLI '{cli}' could not be executed")

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "no output").strip()
            return (None, f"{cli} failed (exit {result.returncode}): {detail}")

        url = backend.extract_url(result.stdout or "", result.stderr or "")
        if url:
            return (url, None)
        return (None, "Deploy succeeded but no URL found in output.")
