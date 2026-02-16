#!/usr/bin/env python3
"""AgentSmith - Web UI server for AgentsOne."""

import os
from flask import Flask, jsonify, request, send_file

from manager.agent import ManagerAgent

app = Flask(__name__)
manager = ManagerAgent()
history = []


@app.route("/")
def index():
    return send_file("AgentSmith.html")


@app.route("/api/agents")
def api_agents():
    agents = [{"name": name, "description": desc} for name, desc in manager.list_agents()]
    return jsonify(agents)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json()
    if not data or not data.get("request", "").strip():
        return jsonify({"error": "Missing request"}), 400

    req = data["request"].strip()
    result = manager.handle(req, dry_run=False)
    result["request"] = req
    history.append(result)
    return jsonify(result)


@app.route("/api/dry-run", methods=["POST"])
def api_dry_run():
    data = request.get_json()
    if not data or not data.get("request", "").strip():
        return jsonify({"error": "Missing request"}), 400

    req = data["request"].strip()
    result = manager.handle(req, dry_run=True)
    result["request"] = req
    return jsonify(result)


@app.route("/api/history")
def api_history():
    return jsonify(history)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"AgentSmith running at http://localhost:{port}")
    app.run(debug=False, port=port)
