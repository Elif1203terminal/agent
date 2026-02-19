"""IDORTemplateGenerator — static analysis + IDOR test stub generation.

Scans generated source files for routes with integer ID path parameters
(Flask: ``<int:xxx>``; FastAPI: ``{xxx}`` where name contains "id") and
writes a ``tests/test_idor.py`` stub file so developers know which
endpoints need cross-user access testing.

No LLM calls. No network calls. Pure string analysis.
"""

import os
import re

from core.state import PipelineState, FileEntry, Issue

# Stacks that use HTTP routes with path parameters
_HTTP_STACKS = {"flask", "fastapi"}

# Flask: @<expr>.route("<path>"[, methods=[...]])
_FLASK_ROUTE_RE = re.compile(
    r"""@[\w.]+\.route\(\s*["'](.*?)["'](.*?)\)""",
    re.DOTALL,
)

# FastAPI: @<expr>.(get|post|put|delete|patch)("<path>")
_FASTAPI_ROUTE_RE = re.compile(
    r"""@[\w.]+\.(get|post|put|delete|patch)\(\s*["'](.*?)["']""",
    re.IGNORECASE,
)

# Matches {word_containing_id} (case-insensitive)
_FASTAPI_ID_PARAM_RE = re.compile(r"\{(\w*[Ii][Dd]\w*)\}")

# methods=[...] inside a Flask route decorator
_METHODS_RE = re.compile(r"methods\s*=\s*\[([^\]]*)\]")

# function definition — optional async prefix
_DEF_RE = re.compile(r"(?:async\s+)?def\s+(\w+)")


class IDORTemplateGenerator:
    """Generate IDOR test stubs for Flask/FastAPI routes with integer path params."""

    name = "idor_template"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, state: PipelineState, work_dir: str) -> list:
        """Return a list of Issue (possibly empty). Side-effect: writes file."""
        if state.stack not in _HTTP_STACKS:
            return []

        # Idempotency: skip if stub already generated
        if any(f.path == "tests/test_idor.py" for f in state.current_files):
            return []

        routes = self._find_routes(state)
        if not routes:
            return []

        content = self._generate_stub_file(state.stack, routes)

        # Write to disk
        os.makedirs(os.path.join(work_dir, "tests"), exist_ok=True)
        with open(os.path.join(work_dir, "tests", "test_idor.py"), "w") as fp:
            fp.write(content)

        # Add to state so it appears in project output
        state.current_files.append(
            FileEntry(path="tests/test_idor.py", content=content, language="python")
        )

        n_tests = sum(len(r["methods"]) for r in routes)
        return [Issue(
            source="idor_template",
            severity="info",
            file="tests/test_idor.py",
            line=None,
            message=(
                f"Generated {n_tests} IDOR test stub(s) for {len(routes)} route(s) "
                "— see tests/test_idor.py"
            ),
            suggestion=(
                "Configure BASE_URL and credentials, "
                "then run: pytest tests/test_idor.py -v"
            ),
        )]

    # ------------------------------------------------------------------
    # Route detection
    # ------------------------------------------------------------------

    def _find_routes(self, state: PipelineState) -> list:
        """Return deduplicated route dicts from all .py files in state."""
        seen_paths: set = set()
        routes: list = []

        for f in state.current_files:
            if not f.path.endswith(".py"):
                continue
            if state.stack == "flask":
                found = self._find_flask_routes(f.content)
            else:
                found = self._find_fastapi_routes(f.content)

            for route in found:
                if route["path"] not in seen_paths:
                    seen_paths.add(route["path"])
                    routes.append(route)

        return routes

    def _find_flask_routes(self, content: str) -> list:
        """Detect Flask routes with <int:param> path parameters."""
        routes = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            m = _FLASK_ROUTE_RE.search(line)
            if not m:
                continue
            path = m.group(1)
            if "<int:" not in path:
                continue

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

            # Look forward up to 5 lines for the function name
            func_name = "view_func"
            for j in range(i + 1, min(i + 6, len(lines))):
                dm = _DEF_RE.search(lines[j])
                if dm:
                    func_name = dm.group(1)
                    break

            routes.append({"path": path, "methods": methods, "func_name": func_name})

        return routes

    def _find_fastapi_routes(self, content: str) -> list:
        """Detect FastAPI routes where the path contains an id-like parameter."""
        routes = []
        lines = content.splitlines()

        for i, line in enumerate(lines):
            m = _FASTAPI_ROUTE_RE.search(line)
            if not m:
                continue
            method = m.group(1).upper()
            path = m.group(2)

            if not _FASTAPI_ID_PARAM_RE.search(path):
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
    # Stub generation
    # ------------------------------------------------------------------

    def _generate_stub_file(self, stack: str, routes: list) -> str:
        base_url_port = "5000" if stack == "flask" else "8000"

        lines = [
            '"""IDOR test stubs — generated by AgentsOne.',
            "",
            "These stubs are placeholders. Implement each test by:",
            "  1. Creating a resource as User A",
            "  2. Accessing it as User B",
            "  3. Asserting the response is 403 Forbidden",
            '"""',
            "import pytest",
            "import requests  # pip install requests",
            "",
            f'BASE_URL = "http://localhost:{base_url_port}"',
            "",
        ]

        for route in routes:
            path = route["path"]
            methods = sorted(route["methods"])
            class_name = self._path_to_class_name(path)
            method_list = ", ".join(methods)

            lines.append(
                f"# ── {path}  [{method_list}] "
                + "─" * max(0, 76 - len(path) - len(method_list) - 8)
            )
            lines.append("")
            lines.append(f"class {class_name}:")
            lines.append(
                f'    """IDOR: verify cross-user access is denied on {path}."""'
            )
            lines.append("")

            for method in methods:
                method_lower = method.lower()
                lines.append(
                    f"    def test_user_b_cannot_{method_lower}_user_a_resource(self):"
                )
                lines.append(
                    f'        """User B must not {method} another user\'s resource at {path}."""'
                )
                lines.append(
                    '        pytest.skip("Implement: create resource as user_a, '
                    'access as user_b, assert 403")'
                )
                lines.append("        # Steps:")
                lines.append("        # 1. Register/login as User A")
                lines.append(
                    "        # 2. Create a resource → capture the integer ID from the response"
                )
                lines.append("        # 3. Register/login as User B")
                # Build example URL with placeholder
                example_url = _make_example_url(path)
                lines.append(
                    f'        # 4. {method} {{BASE_URL}}{example_url}  '
                    "(replace parameter with captured ID)"
                )
                lines.append("        # 5. assert response.status_code == 403")
                lines.append("")

        return "\n".join(lines) + "\n"

    def _path_to_class_name(self, path: str) -> str:
        """Convert a route path to a valid Python class name.

        Examples:
          "/posts/<int:post_id>"  → "TestIDOR_posts_post_id"
          "/items/{item_id}/sub" → "TestIDOR_items_item_id_sub"
        """
        # Remove leading slash
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
        return f"TestIDOR_{s}" if s else "TestIDOR_root"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_example_url(path: str) -> str:
    """Replace path params with placeholder text for comments."""
    # Flask <int:post_id> → {post_id}
    result = re.sub(r"<int:(\w+)>", r"{\1}", path)
    # FastAPI {item_id} stays as-is (already braces)
    return result
