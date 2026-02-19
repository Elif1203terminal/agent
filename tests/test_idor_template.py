"""Tests for IDORTemplateGenerator — all static, zero network/subprocess calls."""

import os
import pytest
from unittest.mock import patch, MagicMock

from agents.idor_template import IDORTemplateGenerator
from agents.tester import TesterAgent
from core.state import PipelineState, FileEntry, Issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(stack="flask", files=None):
    state = PipelineState(request="test", category="web", stack=stack)
    state.current_files = [
        FileEntry(
            path=path,
            content=content,
            language="python" if path.endswith(".py") else "html",
        )
        for path, content in (files or {}).items()
    ]
    return state


FLASK_INT_ROUTE = """\
from flask import Flask
app = Flask(__name__)

@app.route('/posts/<int:post_id>', methods=['GET', 'DELETE'])
def get_post(post_id):
    return 'ok'
"""

FLASK_STRING_ROUTE = """\
from flask import Flask
app = Flask(__name__)

@app.route('/posts/<string:slug>')
def get_post(slug):
    return 'ok'
"""

FLASK_MULTI_ROUTES = """\
from flask import Flask
app = Flask(__name__)

@app.route('/users/<int:user_id>')
def get_user(user_id):
    return 'ok'

@app.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    return 'ok'
"""

FLASK_NO_METHODS = """\
from flask import Flask
app = Flask(__name__)

@app.route('/posts/<int:post_id>')
def get_post(post_id):
    return 'ok'
"""

FASTAPI_ID_ROUTE = """\
from fastapi import FastAPI
app = FastAPI()

@app.get('/items/{item_id}')
async def read_item(item_id: int):
    return {'item': item_id}
"""

FASTAPI_USERNAME_ROUTE = """\
from fastapi import FastAPI
app = FastAPI()

@app.get('/users/{username}')
async def get_user(username: str):
    return {'user': username}
"""

FASTAPI_CAMELCASE_ROUTE = """\
from fastapi import FastAPI
app = FastAPI()

@app.get('/orders/{userId}')
async def get_order(userId: int):
    return {}
"""

FASTAPI_MULTIPLE_METHODS = """\
from fastapi import FastAPI
app = FastAPI()

@app.get('/posts/{post_id}')
async def read_post(post_id: int):
    return {}

@app.delete('/posts/{post_id}')
async def delete_post(post_id: int):
    return {}
"""


# ---------------------------------------------------------------------------
# TestSkipNonHttpStacks
# ---------------------------------------------------------------------------

class TestSkipNonHttpStacks:
    @pytest.mark.parametrize("stack", ["static", "cli", "data", "script"])
    def test_non_http_stack_returns_empty(self, tmp_path, stack):
        state = _make_state(stack, {"app.py": FLASK_INT_ROUTE})
        gen = IDORTemplateGenerator()
        result = gen.run(state, str(tmp_path))
        assert result == []

    @pytest.mark.parametrize("stack", ["static", "cli", "data", "script"])
    def test_non_http_stack_writes_no_file(self, tmp_path, stack):
        state = _make_state(stack, {"app.py": FLASK_INT_ROUTE})
        gen = IDORTemplateGenerator()
        gen.run(state, str(tmp_path))
        assert not (tmp_path / "tests" / "test_idor.py").exists()


# ---------------------------------------------------------------------------
# TestFlaskRouteDetection
# ---------------------------------------------------------------------------

class TestFlaskRouteDetection:
    def test_int_param_route_detected(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_flask_routes(FLASK_INT_ROUTE)
        assert len(routes) == 1
        assert routes[0]["path"] == "/posts/<int:post_id>"

    def test_string_param_route_not_detected(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_flask_routes(FLASK_STRING_ROUTE)
        assert routes == []

    def test_multiple_int_param_routes_all_detected(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_flask_routes(FLASK_MULTI_ROUTES)
        paths = [r["path"] for r in routes]
        assert "/users/<int:user_id>" in paths
        assert "/items/<int:item_id>" in paths

    def test_methods_extracted_from_decorator(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_flask_routes(FLASK_INT_ROUTE)
        assert set(routes[0]["methods"]) == {"GET", "DELETE"}

    def test_absent_methods_defaults_to_get(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_flask_routes(FLASK_NO_METHODS)
        assert routes[0]["methods"] == ["GET"]

    def test_func_name_extracted(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_flask_routes(FLASK_INT_ROUTE)
        assert routes[0]["func_name"] == "get_post"


# ---------------------------------------------------------------------------
# TestFastAPIRouteDetection
# ---------------------------------------------------------------------------

class TestFastAPIRouteDetection:
    def test_item_id_detected_on_get(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_fastapi_routes(FASTAPI_ID_ROUTE)
        assert len(routes) == 1
        assert routes[0]["path"] == "/items/{item_id}"
        assert routes[0]["methods"] == ["GET"]

    def test_username_not_detected(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_fastapi_routes(FASTAPI_USERNAME_ROUTE)
        assert routes == []

    def test_camelcase_user_id_detected(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_fastapi_routes(FASTAPI_CAMELCASE_ROUTE)
        assert len(routes) == 1
        assert routes[0]["path"] == "/orders/{userId}"

    def test_multiple_http_methods_detected(self):
        gen = IDORTemplateGenerator()
        routes = gen._find_fastapi_routes(FASTAPI_MULTIPLE_METHODS)
        methods = {r["methods"][0] for r in routes}
        assert "GET" in methods
        assert "DELETE" in methods


# ---------------------------------------------------------------------------
# TestStubGeneration
# ---------------------------------------------------------------------------

class TestStubGeneration:
    def test_generated_stub_contains_route_path(self):
        gen = IDORTemplateGenerator()
        routes = [{"path": "/posts/<int:post_id>", "methods": ["GET"], "func_name": "get_post"}]
        content = gen._generate_stub_file("flask", routes)
        assert "/posts/<int:post_id>" in content

    def test_generated_stub_contains_pytest_skip(self):
        gen = IDORTemplateGenerator()
        routes = [{"path": "/posts/<int:post_id>", "methods": ["GET"], "func_name": "get_post"}]
        content = gen._generate_stub_file("flask", routes)
        assert "pytest.skip" in content

    def test_multiple_routes_produce_multiple_classes(self):
        gen = IDORTemplateGenerator()
        routes = [
            {"path": "/posts/<int:post_id>", "methods": ["GET"], "func_name": "a"},
            {"path": "/users/<int:user_id>", "methods": ["DELETE"], "func_name": "b"},
        ]
        content = gen._generate_stub_file("flask", routes)
        assert content.count("class TestIDOR_") == 2

    def test_path_to_class_name_valid_identifier(self):
        gen = IDORTemplateGenerator()
        name = gen._path_to_class_name("/posts/<int:post_id>")
        assert name.isidentifier()
        assert name == "TestIDOR_posts_post_id"

    def test_path_to_class_name_fastapi_braces(self):
        gen = IDORTemplateGenerator()
        name = gen._path_to_class_name("/items/{item_id}/sub")
        assert name.isidentifier()
        assert name == "TestIDOR_items_item_id_sub"

    def test_fastapi_base_url_uses_port_8000(self):
        gen = IDORTemplateGenerator()
        routes = [{"path": "/items/{item_id}", "methods": ["GET"], "func_name": "f"}]
        content = gen._generate_stub_file("fastapi", routes)
        assert "8000" in content

    def test_flask_base_url_uses_port_5000(self):
        gen = IDORTemplateGenerator()
        routes = [{"path": "/posts/<int:post_id>", "methods": ["GET"], "func_name": "f"}]
        content = gen._generate_stub_file("flask", routes)
        assert "5000" in content


# ---------------------------------------------------------------------------
# TestIntegration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_run_writes_file_to_work_dir(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_INT_ROUTE})
        gen = IDORTemplateGenerator()
        gen.run(state, str(tmp_path))
        assert (tmp_path / "tests" / "test_idor.py").exists()

    def test_run_appends_file_entry_to_state(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_INT_ROUTE})
        gen = IDORTemplateGenerator()
        gen.run(state, str(tmp_path))
        paths = [f.path for f in state.current_files]
        assert "tests/test_idor.py" in paths

    def test_run_returns_single_info_issue(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_INT_ROUTE})
        gen = IDORTemplateGenerator()
        issues = gen.run(state, str(tmp_path))
        assert len(issues) == 1
        assert issues[0].severity == "info"
        assert issues[0].source == "idor_template"

    def test_run_returns_empty_when_no_int_routes(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_STRING_ROUTE})
        gen = IDORTemplateGenerator()
        issues = gen.run(state, str(tmp_path))
        assert issues == []

    def test_run_idempotent_second_call_is_noop(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_INT_ROUTE})
        gen = IDORTemplateGenerator()
        # First call
        issues1 = gen.run(state, str(tmp_path))
        file_count_after_first = len(state.current_files)
        # Second call — file already in state
        issues2 = gen.run(state, str(tmp_path))
        assert issues2 == []
        assert len(state.current_files) == file_count_after_first


# ---------------------------------------------------------------------------
# TestWiredIntoTester
# ---------------------------------------------------------------------------

class TestWiredIntoTester:
    def test_idor_issues_appended_to_test_issues(self, tmp_path):
        state = _make_state("flask")  # no .py files → no flake8 loop
        idor_issue = Issue(
            source="idor_template", severity="info", file="tests/test_idor.py",
            line=None, message="Generated 1 IDOR test stub(s)", suggestion="run pytest",
        )

        with patch("agents.tester.RuntimeTester") as MockRT, \
             patch("agents.tester.IDORTemplateGenerator") as MockIDOR, \
             patch("subprocess.run") as mock_run:
            MockRT.return_value.run.return_value = []
            MockIDOR.return_value.run.return_value = [idor_issue]
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            agent = TesterAgent()
            result = agent.run(state, str(tmp_path))

        assert idor_issue in result._test_issues

    def test_idor_generator_returning_empty_adds_no_issues(self, tmp_path):
        state = _make_state("flask")

        with patch("agents.tester.RuntimeTester") as MockRT, \
             patch("agents.tester.IDORTemplateGenerator") as MockIDOR, \
             patch("subprocess.run") as mock_run:
            MockRT.return_value.run.return_value = []
            MockIDOR.return_value.run.return_value = []
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            agent = TesterAgent()
            result = agent.run(state, str(tmp_path))

        idor_issues = [i for i in result._test_issues if i.source == "idor_template"]
        assert idor_issues == []
