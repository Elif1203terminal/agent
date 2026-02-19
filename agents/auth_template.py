"""AuthAbuseTemplateGenerator — rate-limit and token-expiry test stub generation.

Scans generated source files for:
  1. Auth endpoints (login, register, token, etc.) → rate-limit brute-force stubs
  2. Protected endpoints (@login_required, @jwt_required, Depends/Security) →
     token-lifecycle stubs (expired, missing, tampered token).

No LLM calls. No network calls. Pure string analysis.
"""

import os
import re

from core.state import PipelineState, FileEntry, Issue

# Stacks that use HTTP routes
_HTTP_STACKS = {"flask", "fastapi"}

# Flask: @<expr>.route("<path>"[, ...])
_FLASK_ROUTE_RE = re.compile(
    r"""@[\w.]+\.route\(\s*["'](.*?)["'](.*?)\)""",
    re.DOTALL,
)

# FastAPI: @<expr>.(get|post|put|delete|patch)("<path>")
_FASTAPI_ROUTE_RE = re.compile(
    r"""@[\w.]+\.(get|post|put|delete|patch)\(\s*["'](.*?)["']""",
    re.IGNORECASE,
)

# methods=[...] inside a Flask route decorator
_METHODS_RE = re.compile(r"methods\s*=\s*\[([^\]]*)\]")

# function definition — optional async prefix
_DEF_RE = re.compile(r"(?:async\s+)?def\s+(\w+)")

# Path keywords indicating an auth endpoint
_AUTH_PATH_RE = re.compile(
    r"login|logout|register|signup|sign-up|forgot.?password|"
    r"reset.?password|change.?password|refresh|token|auth|verify|resend",
    re.IGNORECASE,
)

# Flask auth decorators
_LOGIN_REQUIRED_RE = re.compile(r"@\w*login_required\b|@\w*jwt_required\b")


class AuthAbuseTemplateGenerator:
    """Generate auth-abuse test stubs for Flask/FastAPI auth and protected routes."""

    name = "auth_abuse_template"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, state: PipelineState, work_dir: str) -> list:
        """Return a list of Issue (possibly empty). Side-effect: writes file."""
        if state.stack not in _HTTP_STACKS:
            return []

        # Idempotency: skip if stub already generated
        if any(f.path == "tests/test_auth_abuse.py" for f in state.current_files):
            return []

        auth_eps = self._find_auth_endpoints(state)
        prot_eps = self._find_protected_endpoints(state)

        if not auth_eps and not prot_eps:
            return []

        content = self._generate_stub_file(state.stack, auth_eps, prot_eps)

        # Write to disk
        os.makedirs(os.path.join(work_dir, "tests"), exist_ok=True)
        with open(os.path.join(work_dir, "tests", "test_auth_abuse.py"), "w") as fp:
            fp.write(content)

        # Add to state so it appears in project output
        state.current_files.append(
            FileEntry(path="tests/test_auth_abuse.py", content=content, language="python")
        )

        n_rate = len(auth_eps)
        n_expiry = len(prot_eps) * 3
        return [Issue(
            source="auth_abuse_template",
            severity="info",
            file="tests/test_auth_abuse.py",
            line=None,
            message=(
                f"Generated {n_rate} rate-limit and {n_expiry} token-lifecycle "
                "stub(s) — see tests/test_auth_abuse.py"
            ),
            suggestion=(
                "Configure BASE_URL and credentials, "
                "then run: pytest tests/test_auth_abuse.py -v"
            ),
        )]

    # ------------------------------------------------------------------
    # Auth endpoint detection
    # ------------------------------------------------------------------

    def _find_auth_endpoints(self, state: PipelineState) -> list:
        """Return deduplicated auth-endpoint dicts from all .py files in state."""
        seen: set = set()
        endpoints: list = []

        for f in state.current_files:
            if not f.path.endswith(".py"):
                continue
            if state.stack == "flask":
                found = self._find_flask_auth_endpoints(f.content)
            else:
                found = self._find_fastapi_auth_endpoints(f.content)

            for ep in found:
                if ep["path"] not in seen:
                    seen.add(ep["path"])
                    endpoints.append(ep)

        return endpoints

    def _find_flask_auth_endpoints(self, content: str) -> list:
        """Detect Flask routes whose path matches auth keywords."""
        routes = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            m = _FLASK_ROUTE_RE.search(line)
            if not m:
                continue
            path = m.group(1)
            if not _AUTH_PATH_RE.search(path):
                continue

            # Extract methods; default POST for auth endpoints
            rest = m.group(2)
            mm = _METHODS_RE.search(rest)
            if mm:
                methods = [
                    meth.strip().strip("'\"").upper()
                    for meth in mm.group(1).split(",")
                    if meth.strip().strip("'\"")
                ]
            else:
                methods = ["POST"]

            # Look forward up to 5 lines for the function name
            func_name = "view_func"
            for j in range(i + 1, min(i + 6, len(lines))):
                dm = _DEF_RE.search(lines[j])
                if dm:
                    func_name = dm.group(1)
                    break

            routes.append({"path": path, "methods": methods, "func_name": func_name})

        return routes

    def _find_fastapi_auth_endpoints(self, content: str) -> list:
        """Detect FastAPI routes whose path matches auth keywords."""
        routes = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            m = _FASTAPI_ROUTE_RE.search(line)
            if not m:
                continue
            method = m.group(1).upper()
            path = m.group(2)
            if not _AUTH_PATH_RE.search(path):
                continue

            # Look forward up to 5 lines for the function name
            func_name = "endpoint"
            for j in range(i + 1, min(i + 6, len(lines))):
                dm = _DEF_RE.search(lines[j])
                if dm:
                    func_name = dm.group(1)
                    break

            routes.append({"path": path, "methods": [method], "func_name": func_name})

        return routes

    # ------------------------------------------------------------------
    # Protected endpoint detection
    # ------------------------------------------------------------------

    def _find_protected_endpoints(self, state: PipelineState) -> list:
        """Return deduplicated protected-endpoint dicts from all .py files in state."""
        seen: set = set()
        endpoints: list = []

        for f in state.current_files:
            if not f.path.endswith(".py"):
                continue
            if state.stack == "flask":
                found = self._find_flask_protected_endpoints(f.content)
            else:
                found = self._find_fastapi_protected_endpoints(f.content)

            for ep in found:
                if ep["path"] not in seen:
                    seen.add(ep["path"])
                    endpoints.append(ep)

        return endpoints

    def _find_flask_protected_endpoints(self, content: str) -> list:
        """Detect Flask routes followed by @login_required or @jwt_required."""
        routes = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            m = _FLASK_ROUTE_RE.search(line)
            if not m:
                continue
            path = m.group(1)

            # Look forward ≤10 lines for auth decorator and def
            found_auth = False
            func_name = "view_func"
            for j in range(i + 1, min(i + 11, len(lines))):
                if _LOGIN_REQUIRED_RE.search(lines[j]):
                    found_auth = True
                dm = _DEF_RE.search(lines[j])
                if dm:
                    func_name = dm.group(1)
                    break

            if not found_auth:
                continue

            # Extract methods; default GET for protected endpoints
            rest = m.group(2)
            mm = _METHODS_RE.search(rest)
            if mm:
                methods = [
                    meth.strip().strip("'\"").upper()
                    for meth in mm.group(1).split(",")
                    if meth.strip().strip("'\"")
                ]
            else:
                methods = ["GET"]

            routes.append({"path": path, "methods": methods, "func_name": func_name})

        return routes

    def _find_fastapi_protected_endpoints(self, content: str) -> list:
        """Detect FastAPI routes whose handler uses Depends( or = Security(."""
        routes = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            m = _FASTAPI_ROUTE_RE.search(line)
            if not m:
                continue
            method = m.group(1).upper()
            path = m.group(2)

            # Look forward ≤10 lines for def/async def
            func_name = "endpoint"
            def_line_idx = None
            for j in range(i + 1, min(i + 11, len(lines))):
                dm = _DEF_RE.search(lines[j])
                if dm:
                    func_name = dm.group(1)
                    def_line_idx = j
                    break

            if def_line_idx is None:
                continue

            # Check the def line and next 3 lines for Depends( or = Security(
            found_auth = False
            for k in range(def_line_idx, min(def_line_idx + 4, len(lines))):
                if "Depends(" in lines[k] or "= Security(" in lines[k]:
                    found_auth = True
                    break

            if not found_auth:
                continue

            routes.append({"path": path, "methods": [method], "func_name": func_name})

        return routes

    # ------------------------------------------------------------------
    # Stub generation
    # ------------------------------------------------------------------

    def _generate_stub_file(self, stack: str, auth_eps: list, prot_eps: list) -> str:
        """Generate the test stub file content."""
        base_url_port = "5000" if stack == "flask" else "8000"

        lines = [
            '"""Auth abuse test stubs — generated by AgentsOne."""',
            "import pytest",
            "import requests  # pip install requests",
            "",
            f'BASE_URL = "http://localhost:{base_url_port}"',
            "",
        ]

        for ep in auth_eps:
            path = ep["path"]
            methods = sorted(ep["methods"])
            primary = methods[0]
            class_name = self._path_to_class_name(path, "TestRateLimit")
            method_list = ", ".join(methods)

            lines.append(
                f"# ── {path}  [{method_list}] "
                + "─" * max(0, 76 - len(path) - len(method_list) - 8)
            )
            lines.append("")
            lines.append(f"class {class_name}:")
            lines.append(
                f'    """Rate-limit: verify {path} is protected against brute-force."""'
            )
            lines.append("")
            lines.append("    def test_brute_force_triggers_rate_limit(self):")
            lines.append(
                f'        """Repeated failed {primary} {path} attempts must eventually return 429."""'
            )
            lines.append(
                '        pytest.skip("Implement: send repeated bad-credential requests, assert 429")'
            )
            lines.append("        # Steps:")
            lines.append("        # 1. Choose a registered user's email/username")
            lines.append(
                f"        # 2. {primary} {{BASE_URL}}{path} with wrong password 10+ times"
            )
            lines.append(
                "        # 3. assert that at some point response.status_code == 429"
            )
            lines.append("")

        for ep in prot_eps:
            path = ep["path"]
            methods = sorted(ep["methods"])
            primary = methods[0]
            class_name = self._path_to_class_name(path, "TestTokenExpiry")
            method_list = ", ".join(methods)

            lines.append(
                f"# ── {path}  [{method_list}] "
                + "─" * max(0, 76 - len(path) - len(method_list) - 8)
            )
            lines.append("")
            lines.append(f"class {class_name}:")
            lines.append(
                f'    """Token expiry/validity: verify {path} enforces token lifecycle."""'
            )
            lines.append("")
            lines.append("    def test_expired_token_returns_401(self):")
            lines.append(
                '        pytest.skip("Implement: request with expired token, assert 401")'
            )
            lines.append("        # Steps:")
            lines.append("        # 1. Obtain a valid token")
            lines.append(
                "        # 2. Wait for expiry OR use a known-expired token string"
            )
            lines.append(
                f"        # 3. {primary} {{BASE_URL}}{path}  Authorization: Bearer <expired_token>"
            )
            lines.append("        # 4. assert response.status_code == 401")
            lines.append("")
            lines.append("    def test_missing_token_returns_401(self):")
            lines.append(
                '        pytest.skip("Implement: request with no auth header, assert 401")'
            )
            lines.append("        # Steps:")
            lines.append(
                f"        # 1. {primary} {{BASE_URL}}{path}  (no Authorization header)"
            )
            lines.append("        # 2. assert response.status_code == 401")
            lines.append("")
            lines.append("    def test_tampered_token_returns_401(self):")
            lines.append(
                '        pytest.skip("Implement: request with tampered token, assert 401")'
            )
            lines.append("        # Steps:")
            lines.append("        # 1. Obtain a valid JWT token")
            lines.append(
                "        # 2. Replace the last character of the signature with 'X'"
            )
            lines.append(
                f"        # 3. {primary} {{BASE_URL}}{path}  Authorization: Bearer <tampered_token>"
            )
            lines.append("        # 4. assert response.status_code == 401")
            lines.append("")

        return "\n".join(lines) + "\n"

    def _path_to_class_name(self, path: str, prefix: str) -> str:
        """Convert a route path to a valid Python class name with given prefix.

        Examples:
          ("/login", "TestRateLimit")    → "TestRateLimit_login"
          ("/api/me", "TestTokenExpiry") → "TestTokenExpiry_api_me"
        """
        s = path.lstrip("/")
        # Replace <int:xxx> with xxx
        s = re.sub(r"<int:(\w+)>", r"\1", s)
        # Replace {xxx} with xxx
        s = re.sub(r"\{(\w+)\}", r"\1", s)
        # Replace remaining <...> (other param types)
        s = re.sub(r"<[^>]*>", "_", s)
        # Replace non-alnum chars with underscore
        s = re.sub(r"[^\w]", "_", s)
        # Collapse consecutive underscores
        s = re.sub(r"_+", "_", s)
        # Strip leading/trailing underscores
        s = s.strip("_")
        return f"{prefix}_{s}" if s else f"{prefix}_root"
