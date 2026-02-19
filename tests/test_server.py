"""Tests for server.py Flask endpoints — all orchestrator calls are mocked."""

import json
import pytest
from unittest.mock import patch, MagicMock

from core.state import PipelineState, FileEntry, Issue, Iteration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(status="done", iterations=0, max_iterations=5):
    state = PipelineState(
        request="build a todo app",
        category="web",
        stack="flask",
        spec="A simple todo app",
        file_manifest=["app.py"],
        max_iterations=max_iterations,
        output_dir="/tmp/test_output",
    )
    state.status = status
    state.current_files = [
        FileEntry(path="app.py", content="print('hello')", language="python")
    ]
    for i in range(iterations):
        state.iterations.append(Iteration(
            number=i + 1,
            files=list(state.current_files),
            issues=[],
            lint_passed=True,
            tests_passed=True,
            security_passed=True,
        ))
    return state


@pytest.fixture
def client():
    """Flask test client with a fresh job store each test."""
    import server
    server.app.config["TESTING"] = True
    server._jobs.clear()
    server.history.clear()
    with server.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

def test_index_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"html" in resp.data.lower()


# ---------------------------------------------------------------------------
# GET /api/agents
# ---------------------------------------------------------------------------

def test_api_agents_returns_list(client):
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    names = [a["name"] for a in data]
    assert "planner" in names
    assert "generator" in names
    assert "security" in names


# ---------------------------------------------------------------------------
# POST /api/generate
# ---------------------------------------------------------------------------

def test_generate_missing_request(client):
    resp = client.post("/api/generate", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_generate_empty_request(client):
    resp = client.post("/api/generate", json={"request": "   "})
    assert resp.status_code == 400


def test_generate_success(client):
    state = _make_state(status="done")

    with patch("server.orchestrator.create_state", return_value=state), \
         patch("server.orchestrator.plan", return_value=state), \
         patch("server.orchestrator.run_iteration", return_value=state), \
         patch("server.orchestrator.generate_readme", return_value=state), \
         patch("server.orchestrator.write_files", return_value=["app.py"]):

        resp = client.post("/api/generate", json={"request": "build a todo app"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert "job_id" in data
    assert data["request"] == "build a todo app"


def test_generate_awaiting_approval_skips_write(client):
    """When quality gates fail, files should NOT be written yet."""
    state = _make_state(status="awaiting_approval", iterations=1)

    with patch("server.orchestrator.create_state", return_value=state), \
         patch("server.orchestrator.plan", return_value=state), \
         patch("server.orchestrator.run_iteration", return_value=state), \
         patch("server.orchestrator.write_files") as mock_write:

        resp = client.post("/api/generate", json={"request": "build something"})

    assert resp.status_code == 200
    mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/iterate
# ---------------------------------------------------------------------------

def test_iterate_missing_job_id(client):
    resp = client.post("/api/iterate", json={})
    assert resp.status_code == 400


def test_iterate_unknown_job_id(client):
    resp = client.post("/api/iterate", json={"job_id": "notreal"})
    assert resp.status_code == 404


def test_iterate_already_done(client):
    import server
    state = _make_state(status="done")
    job_id = server._store_job(state)

    resp = client.post("/api/iterate", json={"job_id": job_id})
    assert resp.status_code == 400
    assert "completed" in resp.get_json()["error"].lower()


def test_iterate_at_limit_returns_400(client):
    """If iterations == effective_max, iterate should refuse."""
    import server
    state = _make_state(status="awaiting_approval", iterations=5, max_iterations=5)
    job_id = server._store_job(state)

    resp = client.post("/api/iterate", json={"job_id": job_id})
    assert resp.status_code == 400
    assert "limit" in resp.get_json()["error"].lower()


def test_iterate_success(client):
    import server
    state = _make_state(status="awaiting_approval", iterations=1)
    job_id = server._store_job(state)

    done_state = _make_state(status="done", iterations=2)

    with patch("server.orchestrator.run_iteration", return_value=done_state), \
         patch("server.orchestrator.generate_readme", return_value=done_state), \
         patch("server.orchestrator.write_files", return_value=["app.py"]):

        resp = client.post("/api/iterate", json={"job_id": job_id})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["job_id"] == job_id


# ---------------------------------------------------------------------------
# POST /api/approve
# ---------------------------------------------------------------------------

def test_approve_missing_job_id(client):
    resp = client.post("/api/approve", json={})
    assert resp.status_code == 400


def test_approve_unknown_job_id(client):
    resp = client.post("/api/approve", json={"job_id": "notreal"})
    assert resp.status_code == 404


def test_approve_success(client):
    import server
    state = _make_state(status="awaiting_approval", iterations=1)
    job_id = server._store_job(state)

    with patch("server.orchestrator.generate_readme", return_value=state), \
         patch("server.orchestrator.write_files", return_value=["app.py"]):

        resp = client.post("/api/approve", json={"job_id": job_id})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["written_files"] == ["app.py"]


# ---------------------------------------------------------------------------
# POST /api/dry-run
# ---------------------------------------------------------------------------

def test_dry_run_missing_request(client):
    resp = client.post("/api/dry-run", json={})
    assert resp.status_code == 400


def test_dry_run_success(client):
    state = _make_state()
    state.spec = "A simple todo app spec"
    state.file_manifest = ["app.py", "templates/index.html"]

    with patch("server.orchestrator.create_state", return_value=state), \
         patch("server.orchestrator.plan", return_value=state):

        resp = client.post("/api/dry-run", json={"request": "build a todo app"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["dry_run"] is True
    assert "spec" in data
    assert "file_manifest" in data


# ---------------------------------------------------------------------------
# GET /api/status/<job_id>
# ---------------------------------------------------------------------------

def test_status_unknown_job(client):
    resp = client.get("/api/status/notreal")
    assert resp.status_code == 404


def test_status_known_job(client):
    import server
    state = _make_state(status="done")
    job_id = server._store_job(state)

    resp = client.get(f"/api/status/{job_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["job_id"] == job_id


# ---------------------------------------------------------------------------
# GET /api/history
# ---------------------------------------------------------------------------

def test_history_empty(client):
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_history_after_generate(client):
    state = _make_state(status="done")

    with patch("server.orchestrator.create_state", return_value=state), \
         patch("server.orchestrator.plan", return_value=state), \
         patch("server.orchestrator.run_iteration", return_value=state), \
         patch("server.orchestrator.generate_readme", return_value=state), \
         patch("server.orchestrator.write_files", return_value=[]):

        client.post("/api/generate", json={"request": "build a todo app"})

    resp = client.get("/api/history")
    assert resp.status_code == 200
    history = resp.get_json()
    assert len(history) == 1
    assert history[0]["request"] == "build a todo app"
