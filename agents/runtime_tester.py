"""RuntimeTester — starts a generated Flask/FastAPI server and runs HTTP probes."""

import os
import socket
import subprocess
import time
import urllib.request
import urllib.error

from core.state import PipelineState, Issue

# Only these stacks get runtime HTTP probes
_HTTP_STACKS = {"flask", "fastapi"}

_FLASK_CANDIDATES = ["app.py", "main.py", "wsgi.py", "run.py"]
_FASTAPI_CANDIDATES = ["app.py", "main.py", "api.py"]

_SECURITY_HEADERS = [
    "X-Frame-Options",
    "X-Content-Type-Options",
    "X-XSS-Protection",
]

_SENSITIVE_PATHS = ["/.env", "/.git/config", "/config.py", "/secrets.py"]

_DEBUG_INDICATORS = [
    "Werkzeug Debugger",
    "Traceback (most recent call last)",
    "Interactive Console",
]


class RuntimeTester:
    """Starts a Flask/FastAPI server and runs generic HTTP probes.

    Only probes stacks in _HTTP_STACKS. Reuses the .venv created by TesterAgent.
    Uses stdlib urllib — zero new dependencies.
    """

    name = "runtime"

    def run(self, state: PipelineState, work_dir: str) -> list:
        """Run HTTP probes if this is an HTTP stack. Returns list of Issue."""
        if state.stack not in _HTTP_STACKS:
            return []

        if os.name == "nt":
            python = os.path.join(work_dir, ".venv", "Scripts", "python")
        else:
            python = os.path.join(work_dir, ".venv", "bin", "python")

        if not os.path.isfile(python):
            return []

        port = self._free_port()
        if port is None:
            return []

        proc = self._start_server(state, work_dir, python, port)
        if proc is None:
            return []

        try:
            if not self._wait_ready(port):
                return [Issue(
                    source="runtime",
                    severity="warning",
                    file="app.py",
                    line=None,
                    message="Server did not start within timeout",
                    suggestion="Check that the app starts without errors",
                )]
            base_url = f"http://127.0.0.1:{port}"
            return self._run_probes(base_url, state)
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                pass

    def _free_port(self) -> int | None:
        """Return a free TCP port assigned by the OS."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]
        except OSError:
            return None

    def _start_server(self, state, work_dir, python, port):
        """Start the app subprocess. Returns Popen or None on failure."""
        bin_dir = os.path.dirname(python)
        entry = self._find_entry(
            state,
            _FLASK_CANDIDATES if state.stack == "flask" else _FASTAPI_CANDIDATES,
        )

        if state.stack == "flask":
            flask_bin = os.path.join(bin_dir, "flask")
            cmd = [flask_bin, "run", "--port", str(port), "--no-debugger", "--no-reload"]
            env = os.environ.copy()
            env["FLASK_APP"] = entry
            env["FLASK_ENV"] = "testing"
        else:
            uvicorn_bin = os.path.join(bin_dir, "uvicorn")
            module = entry.replace(".py", "").replace("/", ".").replace("\\", ".")
            cmd = [uvicorn_bin, f"{module}:app", "--port", str(port), "--no-access-log"]
            env = os.environ.copy()

        try:
            return subprocess.Popen(
                cmd,
                cwd=work_dir,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, PermissionError):
            return None

    def _wait_ready(self, port, timeout=15, interval=0.2) -> bool:
        """Poll until server responds or timeout expires. Returns True if up."""
        url = f"http://127.0.0.1:{port}/"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1) as _:
                    return True
            except urllib.error.HTTPError:
                # Any HTTP response (even 4xx) means the server is up
                return True
            except Exception:
                time.sleep(interval)
        return False

    def _run_probes(self, base_url, state) -> list:
        """Run all generic probes and return combined Issue list."""
        issues = []
        issues.extend(self._probe_security_headers(base_url))
        issues.extend(self._probe_debug_mode(base_url))
        issues.extend(self._probe_cors_wildcard(base_url))
        issues.extend(self._probe_sensitive_paths(base_url))
        return issues

    def _probe_security_headers(self, base_url) -> list:
        """Check that common security headers are present on GET /."""
        resp, body, status = self._get(f"{base_url}/")
        if resp is None:
            return []
        issues = []
        for header in _SECURITY_HEADERS:
            if not resp.headers.get(header):
                issues.append(Issue(
                    source="runtime",
                    severity="warning",
                    file="app.py",
                    line=None,
                    message=f"Missing security header: {header}",
                    suggestion=f"Add '{header}' to all responses via after_request or middleware",
                ))
        return issues

    def _probe_debug_mode(self, base_url) -> list:
        """Check that debug mode is not active (Werkzeug debugger not exposed)."""
        resp, body, status = self._get(f"{base_url}/_agentsone_probe_404")
        for indicator in _DEBUG_INDICATORS:
            if indicator in body:
                return [Issue(
                    source="runtime",
                    severity="error",
                    file="app.py",
                    line=None,
                    message=f"Debug mode is active: '{indicator}' found in 404 response",
                    suggestion="Set debug=False and FLASK_ENV=production before deploying",
                )]
        return []

    def _probe_cors_wildcard(self, base_url) -> list:
        """Check that CORS wildcard is not returned for a cross-origin request."""
        resp, body, status = self._get(
            f"{base_url}/",
            headers={"Origin": "http://evil.example.com"},
        )
        if resp is None:
            return []
        cors = resp.headers.get("Access-Control-Allow-Origin", "")
        if cors == "*":
            return [Issue(
                source="runtime",
                severity="warning",
                file="app.py",
                line=None,
                message="CORS wildcard (Access-Control-Allow-Origin: *) returned for cross-origin request",
                suggestion="Restrict CORS to explicit origins using Flask-CORS or equivalent",
            )]
        return []

    def _probe_sensitive_paths(self, base_url) -> list:
        """Check that sensitive paths return 404 (not 200)."""
        issues = []
        for path in _SENSITIVE_PATHS:
            resp, body, status = self._get(f"{base_url}{path}")
            if status == 200:
                issues.append(Issue(
                    source="runtime",
                    severity="error",
                    file=path.lstrip("/"),
                    line=None,
                    message=f"Sensitive path is publicly accessible: {path}",
                    suggestion=f"Block access to {path} — do not serve this file publicly",
                ))
        return issues

    def _get(self, url, headers=None, timeout=5):
        """GET url, return (resp_or_err, body_text, status_code).

        Returns (None, "", -1) on connection failure.
        Handles both successful (2xx) and error (4xx/5xx) HTTP responses.
        """
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return resp, body, resp.status
        except urllib.error.HTTPError as e:
            # Non-2xx response — still a valid HTTP response; headers are available
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            return e, body, e.code
        except Exception:
            return None, "", -1

    def _find_entry(self, state, candidates) -> str:
        """Return the first candidate that exists in state.current_files."""
        paths = {f.path for f in state.current_files}
        for c in candidates:
            if c in paths:
                return c
        return candidates[0]  # fallback to first candidate
