"""Tests for AuthAbuseTemplateGenerator — all static, zero network/subprocess calls."""

import os
import pytest
from unittest.mock import patch, MagicMock

from agents.auth_template import AuthAbuseTemplateGenerator
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


# ---------------------------------------------------------------------------
# Fixture content
# ---------------------------------------------------------------------------

FLASK_LOGIN_ROUTE = """\
from flask import Flask
app = Flask(__name__)

@app.route('/login', methods=['POST'])
def login():
    return 'ok'
"""

FLASK_RESET_PASSWORD_ROUTE = """\
from flask import Flask
app = Flask(__name__)

@app.route('/reset-password', methods=['POST'])
def reset_password():
    return 'ok'
"""

FLASK_NON_AUTH_ROUTE = """\
from flask import Flask
app = Flask(__name__)

@app.route('/items')
def list_items():
    return 'ok'
"""

FLASK_MULTI_AUTH_ROUTES = """\
from flask import Flask
app = Flask(__name__)

@app.route('/login', methods=['POST'])
def login():
    return 'ok'

@app.route('/register', methods=['POST'])
def register():
    return 'ok'
"""

FLASK_AUTH_NO_METHODS = """\
from flask import Flask
app = Flask(__name__)

@app.route('/auth/verify')
def verify():
    return 'ok'
"""

FLASK_LOGIN_REQUIRED = """\
from flask import Flask
from flask_login import login_required
app = Flask(__name__)

@app.route('/dashboard')
@login_required
def dashboard():
    return 'ok'
"""

FLASK_NO_AUTH_DECORATOR = """\
from flask import Flask
app = Flask(__name__)

@app.route('/public')
def public():
    return 'ok'
"""

FLASK_JWT_REQUIRED = """\
from flask import Flask
from flask_jwt_extended import jwt_required
app = Flask(__name__)

@app.route('/api/me')
@jwt_required()
def me():
    return 'ok'
"""

FASTAPI_TOKEN_ROUTE = """\
from fastapi import FastAPI
app = FastAPI()

@app.post('/token')
async def get_token():
    return {}
"""

FASTAPI_ITEMS_ROUTE = """\
from fastapi import FastAPI
app = FastAPI()

@app.get('/items')
async def list_items():
    return []
"""

FASTAPI_AUTH_LOGIN_ROUTE = """\
from fastapi import FastAPI
app = FastAPI()

@app.post('/auth/login')
async def auth_login():
    return {}
"""

FASTAPI_DEPENDS_ROUTE = """\
from fastapi import FastAPI, Depends
app = FastAPI()

@app.get('/api/me')
async def get_me(current_user=Depends(get_current_user)):
    return {}
"""

FASTAPI_NO_DEPENDS_ROUTE = """\
from fastapi import FastAPI
app = FastAPI()

@app.get('/api/public')
async def public():
    return {}
"""

FASTAPI_SECURITY_ROUTE = """\
from fastapi import FastAPI, Security
app = FastAPI()

@app.get('/api/admin')
async def admin(user = Security(get_current_active_user, scopes=["admin"])):
    return {}
"""


# ---------------------------------------------------------------------------
# TestSkipNonHttpStacks
# ---------------------------------------------------------------------------

class TestSkipNonHttpStacks:
    @pytest.mark.parametrize("stack", ["static", "cli", "data", "script"])
    def test_non_http_stack_returns_empty_and_writes_no_file(self, tmp_path, stack):
        state = _make_state(stack, {"app.py": FLASK_LOGIN_ROUTE})
        gen = AuthAbuseTemplateGenerator()
        result = gen.run(state, str(tmp_path))
        assert result == []
        assert not (tmp_path / "tests" / "test_auth_abuse.py").exists()


# ---------------------------------------------------------------------------
# TestAuthEndpointDetection_Flask
# ---------------------------------------------------------------------------

class TestAuthEndpointDetection_Flask:
    def test_login_route_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_flask_auth_endpoints(FLASK_LOGIN_ROUTE)
        assert len(eps) == 1
        assert eps[0]["path"] == "/login"

    def test_reset_password_route_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_flask_auth_endpoints(FLASK_RESET_PASSWORD_ROUTE)
        assert len(eps) == 1
        assert eps[0]["path"] == "/reset-password"

    def test_non_auth_path_not_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_flask_auth_endpoints(FLASK_NON_AUTH_ROUTE)
        assert eps == []

    def test_multiple_auth_routes_all_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_flask_auth_endpoints(FLASK_MULTI_AUTH_ROUTES)
        paths = [e["path"] for e in eps]
        assert "/login" in paths
        assert "/register" in paths

    def test_absent_methods_defaults_to_post(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_flask_auth_endpoints(FLASK_AUTH_NO_METHODS)
        assert len(eps) == 1
        assert eps[0]["methods"] == ["POST"]


# ---------------------------------------------------------------------------
# TestAuthEndpointDetection_FastAPI
# ---------------------------------------------------------------------------

class TestAuthEndpointDetection_FastAPI:
    def test_post_token_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_fastapi_auth_endpoints(FASTAPI_TOKEN_ROUTE)
        assert len(eps) == 1
        assert eps[0]["path"] == "/token"
        assert eps[0]["methods"] == ["POST"]

    def test_get_items_not_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_fastapi_auth_endpoints(FASTAPI_ITEMS_ROUTE)
        assert eps == []

    def test_post_auth_login_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_fastapi_auth_endpoints(FASTAPI_AUTH_LOGIN_ROUTE)
        assert len(eps) == 1
        assert eps[0]["path"] == "/auth/login"


# ---------------------------------------------------------------------------
# TestProtectedEndpointDetection_Flask
# ---------------------------------------------------------------------------

class TestProtectedEndpointDetection_Flask:
    def test_login_required_route_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_flask_protected_endpoints(FLASK_LOGIN_REQUIRED)
        assert len(eps) == 1
        assert eps[0]["path"] == "/dashboard"

    def test_route_without_auth_decorator_not_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_flask_protected_endpoints(FLASK_NO_AUTH_DECORATOR)
        assert eps == []

    def test_jwt_required_route_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_flask_protected_endpoints(FLASK_JWT_REQUIRED)
        assert len(eps) == 1
        assert eps[0]["path"] == "/api/me"


# ---------------------------------------------------------------------------
# TestProtectedEndpointDetection_FastAPI
# ---------------------------------------------------------------------------

class TestProtectedEndpointDetection_FastAPI:
    def test_depends_route_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_fastapi_protected_endpoints(FASTAPI_DEPENDS_ROUTE)
        assert len(eps) == 1
        assert eps[0]["path"] == "/api/me"

    def test_route_without_depends_not_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_fastapi_protected_endpoints(FASTAPI_NO_DEPENDS_ROUTE)
        assert eps == []

    def test_security_route_detected(self):
        gen = AuthAbuseTemplateGenerator()
        eps = gen._find_fastapi_protected_endpoints(FASTAPI_SECURITY_ROUTE)
        assert len(eps) == 1
        assert eps[0]["path"] == "/api/admin"


# ---------------------------------------------------------------------------
# TestStubGeneration
# ---------------------------------------------------------------------------

class TestStubGeneration:
    def test_auth_stub_contains_route_path_and_skip(self):
        gen = AuthAbuseTemplateGenerator()
        auth_eps = [{"path": "/login", "methods": ["POST"], "func_name": "login"}]
        content = gen._generate_stub_file("flask", auth_eps, [])
        assert "/login" in content
        assert "pytest.skip" in content

    def test_protected_stub_contains_all_three_test_methods(self):
        gen = AuthAbuseTemplateGenerator()
        prot_eps = [{"path": "/api/me", "methods": ["GET"], "func_name": "get_me"}]
        content = gen._generate_stub_file("flask", [], prot_eps)
        assert "test_expired_token_returns_401" in content
        assert "test_missing_token_returns_401" in content
        assert "test_tampered_token_returns_401" in content

    def test_multiple_auth_routes_produce_multiple_rate_limit_classes(self):
        gen = AuthAbuseTemplateGenerator()
        auth_eps = [
            {"path": "/login", "methods": ["POST"], "func_name": "login"},
            {"path": "/register", "methods": ["POST"], "func_name": "register"},
        ]
        content = gen._generate_stub_file("flask", auth_eps, [])
        assert content.count("class TestRateLimit_") == 2

    def test_path_to_class_name_produces_valid_identifier_with_prefix(self):
        gen = AuthAbuseTemplateGenerator()
        name_rate = gen._path_to_class_name("/login", "TestRateLimit")
        assert name_rate.isidentifier()
        assert name_rate == "TestRateLimit_login"

        name_expiry = gen._path_to_class_name("/api/me", "TestTokenExpiry")
        assert name_expiry.isidentifier()
        assert name_expiry == "TestTokenExpiry_api_me"


# ---------------------------------------------------------------------------
# TestIntegration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_run_writes_file_to_work_dir(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_LOGIN_ROUTE})
        gen = AuthAbuseTemplateGenerator()
        gen.run(state, str(tmp_path))
        assert (tmp_path / "tests" / "test_auth_abuse.py").exists()

    def test_run_appends_file_entry_to_state(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_LOGIN_ROUTE})
        gen = AuthAbuseTemplateGenerator()
        gen.run(state, str(tmp_path))
        paths = [f.path for f in state.current_files]
        assert "tests/test_auth_abuse.py" in paths

    def test_run_returns_single_info_issue(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_LOGIN_ROUTE})
        gen = AuthAbuseTemplateGenerator()
        issues = gen.run(state, str(tmp_path))
        assert len(issues) == 1
        assert issues[0].severity == "info"
        assert issues[0].source == "auth_abuse_template"

    def test_run_returns_empty_when_no_auth_or_protected_endpoints(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_NON_AUTH_ROUTE})
        gen = AuthAbuseTemplateGenerator()
        issues = gen.run(state, str(tmp_path))
        assert issues == []

    def test_run_idempotent_second_call_is_noop(self, tmp_path):
        state = _make_state("flask", {"app.py": FLASK_LOGIN_ROUTE})
        gen = AuthAbuseTemplateGenerator()
        issues1 = gen.run(state, str(tmp_path))
        file_count_after_first = len(state.current_files)
        issues2 = gen.run(state, str(tmp_path))
        assert issues2 == []
        assert len(state.current_files) == file_count_after_first


# ---------------------------------------------------------------------------
# TestWiredIntoTester
# ---------------------------------------------------------------------------

class TestWiredIntoTester:
    def test_auth_abuse_issues_appended_to_test_issues(self, tmp_path):
        state = _make_state("flask")
        auth_issue = Issue(
            source="auth_abuse_template", severity="info",
            file="tests/test_auth_abuse.py", line=None,
            message="Generated 1 rate-limit and 0 token-lifecycle stub(s)",
            suggestion="run pytest",
        )

        with patch("agents.tester.RuntimeTester") as MockRT, \
             patch("agents.tester.IDORTemplateGenerator") as MockIDOR, \
             patch("agents.tester.AuthAbuseTemplateGenerator") as MockAuth, \
             patch("subprocess.run") as mock_run:
            MockRT.return_value.run.return_value = []
            MockIDOR.return_value.run.return_value = []
            MockAuth.return_value.run.return_value = [auth_issue]
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            agent = TesterAgent()
            result = agent.run(state, str(tmp_path))

        assert auth_issue in result._test_issues

    def test_auth_generator_returning_empty_adds_no_issues(self, tmp_path):
        state = _make_state("flask")

        with patch("agents.tester.RuntimeTester") as MockRT, \
             patch("agents.tester.IDORTemplateGenerator") as MockIDOR, \
             patch("agents.tester.AuthAbuseTemplateGenerator") as MockAuth, \
             patch("subprocess.run") as mock_run:
            MockRT.return_value.run.return_value = []
            MockIDOR.return_value.run.return_value = []
            MockAuth.return_value.run.return_value = []
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            agent = TesterAgent()
            result = agent.run(state, str(tmp_path))

        auth_issues = [i for i in result._test_issues if i.source == "auth_abuse_template"]
        assert auth_issues == []
