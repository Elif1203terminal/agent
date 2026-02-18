"""Tests for manager.classifier."""

from manager.classifier import classify


def test_web_classification():
    cat, scores = classify("build me a flask website with a dashboard")
    assert cat == "web"
    assert scores["web"] > scores["api"]


def test_api_classification():
    cat, scores = classify("create a REST API with CRUD endpoints using FastAPI")
    assert cat == "api"


def test_cli_classification():
    cat, scores = classify("build a CLI tool with argparse for file management")
    assert cat == "cli"


def test_data_classification():
    cat, scores = classify("analyze this CSV data with pandas and matplotlib")
    assert cat == "data"


def test_script_classification():
    cat, scores = classify("write a backup script that runs on a schedule")
    assert cat == "script"


def test_default_to_script():
    cat, scores = classify("do something completely unrelated")
    assert cat == "script"


def test_scores_are_dict():
    _, scores = classify("hello world")
    assert isinstance(scores, dict)
    assert "web" in scores
    assert "api" in scores


# --- Explicit tech override tests ---

def test_explicit_fastapi_with_space():
    """'use fast api' (with space) should classify as api with fastapi stack."""
    cat, scores = classify("build a dark landing page. Use fast api")
    assert cat == "api"
    assert scores.get("_explicit_stack") == "fastapi"


def test_explicit_fastapi_no_space():
    cat, scores = classify("create an app using fastapi")
    assert cat == "api"
    assert scores.get("_explicit_stack") == "fastapi"


def test_explicit_flask():
    cat, scores = classify("build a todo app with flask")
    assert cat == "web"
    assert scores.get("_explicit_stack") == "flask"


def test_explicit_pandas():
    cat, scores = classify("process this file using pandas")
    assert cat == "data"
    assert scores.get("_explicit_stack") == "data"


def test_explicit_overrides_keyword_score():
    """Even if 'web' keywords score higher, explicit 'fastapi' wins."""
    cat, scores = classify("build a web page template dashboard. Use fast api")
    assert cat == "api"
    assert scores.get("_explicit_stack") == "fastapi"
