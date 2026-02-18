#!/usr/bin/env python3
"""AgentSmith - Web UI server for AgentsOne."""

import os
import threading
import time
import uuid
from flask import Flask, jsonify, request, send_file

from manager.agent import ManagerAgent
from core.orchestrator import Orchestrator
from config.defaults import DEFAULTS
from utils.folder_naming import get_output_dir

app = Flask(__name__)
manager = ManagerAgent()
orchestrator = Orchestrator()
history = []

# In-flight pipeline jobs keyed by job_id: {id: {"state": ..., "created": timestamp}}
_jobs = {}
_jobs_lock = threading.Lock()
_MAX_JOBS = 50  # prevent unbounded memory growth
_JOB_TTL = 3600  # expire jobs after 1 hour


def _cleanup_jobs():
    """Remove expired jobs. Called under _jobs_lock."""
    now = time.time()
    expired = [jid for jid, job in _jobs.items() if now - job["created"] > _JOB_TTL]
    for jid in expired:
        del _jobs[jid]
    # If still over limit, remove oldest
    if len(_jobs) > _MAX_JOBS:
        by_age = sorted(_jobs.items(), key=lambda x: x[1]["created"])
        for jid, _ in by_age[:len(_jobs) - _MAX_JOBS]:
            del _jobs[jid]


def _store_job(state):
    """Store a job and return its ID."""
    job_id = str(uuid.uuid4())[:8]
    with _jobs_lock:
        _cleanup_jobs()
        _jobs[job_id] = {"state": state, "created": time.time()}
    return job_id


def _get_job_state(job_id):
    """Get state for a job ID, or None if not found/expired."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return None
    if time.time() - job["created"] > _JOB_TTL:
        with _jobs_lock:
            _jobs.pop(job_id, None)
        return None
    return job["state"]


def _state_to_dict(state):
    """Serialize PipelineState to JSON-safe dict."""
    iterations = []
    for it in state.iterations:
        iterations.append({
            "number": it.number,
            "files": [{"path": f.path, "language": f.language} for f in it.files],
            "issues": [
                {
                    "source": i.source,
                    "severity": i.severity,
                    "file": i.file,
                    "line": i.line,
                    "message": i.message,
                    "suggestion": i.suggestion,
                }
                for i in it.issues
            ],
            "lint_passed": it.lint_passed,
            "tests_passed": it.tests_passed,
            "security_passed": it.security_passed,
        })

    return {
        "category": state.category,
        "stack": state.stack,
        "spec": state.spec,
        "file_manifest": state.file_manifest,
        "status": state.status,
        "output_dir": state.output_dir,
        "iterations": iterations,
        "files": [f.path for f in state.current_files],
        "total_iterations": len(state.iterations),
        "max_iterations": state.max_iterations,
    }


@app.route("/")
def index():
    return send_file("AgentSmith.html")


@app.route("/api/agents")
def api_agents():
    agents = [{"name": name, "description": desc} for name, desc in manager.list_agents()]
    # Add pipeline agents
    agents.extend([
        {"name": "planner", "description": "Breaks request into spec + file manifest"},
        {"name": "generator", "description": "Generates or patches code files"},
        {"name": "reviewer", "description": "Reviews code for functional errors"},
        {"name": "tester", "description": "Runs lint and import checks (no LLM)"},
        {"name": "security", "description": "Scans for vulnerabilities (no LLM)"},
        {"name": "patch_composer", "description": "Aggregates issues into fix instructions (no LLM)"},
    ])
    return jsonify(agents)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Run the full pipeline (single iteration, no auto-looping).

    The UI can call /api/iterate to approve additional iterations.
    """
    data = request.get_json()
    if not data or not data.get("request", "").strip():
        return jsonify({"error": "Missing request"}), 400

    req = data["request"].strip()
    category = data.get("type")
    max_iters = data.get("max_iterations", 2)

    output_dir = get_output_dir(category or "script", req)

    # create_state enforces hard_max_iterations cap internally
    state = orchestrator.create_state(req, category=category,
                                       max_iterations=max_iters,
                                       output_dir=output_dir)
    state = orchestrator.plan(state)
    state = orchestrator.run_iteration(state)

    # If done (quality gates pass), generate README and write files
    if state.status == "done":
        state = orchestrator.generate_readme(state)
        orchestrator.write_files(state)

    result = _state_to_dict(state)
    result["request"] = req

    job_id = _store_job(state)
    result["job_id"] = job_id

    history.append(result)
    return jsonify(result)


@app.route("/api/iterate", methods=["POST"])
def api_iterate():
    """Human-in-the-loop: approve another iteration for an existing job."""
    data = request.get_json()
    job_id = data.get("job_id")
    if not job_id:
        return jsonify({"error": "Missing job_id"}), 400

    state = _get_job_state(job_id)
    if not state:
        return jsonify({"error": "Job not found or expired"}), 404

    if state.status == "done":
        return jsonify({"error": "Pipeline already completed"}), 400

    # Double-check both soft and hard limits
    hard_max = DEFAULTS["hard_max_iterations"]
    if len(state.iterations) >= state.max_iterations:
        return jsonify({"error": f"Max iterations reached ({state.max_iterations})"}), 400
    if len(state.iterations) >= hard_max:
        return jsonify({"error": f"Hard iteration limit reached ({hard_max})"}), 400

    # run_iteration also checks internally, but belt-and-suspenders
    state = orchestrator.run_iteration(state)

    if state.status == "done":
        state = orchestrator.generate_readme(state)
        orchestrator.write_files(state)

    result = _state_to_dict(state)
    result["job_id"] = job_id
    return jsonify(result)


@app.route("/api/approve", methods=["POST"])
def api_approve():
    """Write files for a job as-is (accept current state)."""
    data = request.get_json()
    job_id = data.get("job_id")
    if not job_id:
        return jsonify({"error": "Missing job_id"}), 400

    state = _get_job_state(job_id)
    if not state:
        return jsonify({"error": "Job not found or expired"}), 404

    state.status = "done"
    state = orchestrator.generate_readme(state)
    written = orchestrator.write_files(state)

    result = _state_to_dict(state)
    result["job_id"] = job_id
    result["written_files"] = written
    return jsonify(result)


@app.route("/api/dry-run", methods=["POST"])
def api_dry_run():
    data = request.get_json()
    if not data or not data.get("request", "").strip():
        return jsonify({"error": "Missing request"}), 400

    req = data["request"].strip()
    category = data.get("type")

    state = orchestrator.create_state(req, category=category)
    state = orchestrator.plan(state)

    return jsonify({
        "request": req,
        "category": state.category,
        "stack": state.stack,
        "spec": state.spec,
        "file_manifest": state.file_manifest,
        "dry_run": True,
    })


@app.route("/api/status/<job_id>")
def api_status(job_id):
    """Check pipeline status for a running job."""
    state = _get_job_state(job_id)
    if not state:
        return jsonify({"error": "Job not found"}), 404
    result = _state_to_dict(state)
    result["job_id"] = job_id
    return jsonify(result)


@app.route("/api/history")
def api_history():
    return jsonify(history)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"AgentSmith running at http://localhost:{port}")
    app.run(debug=False, port=port)
