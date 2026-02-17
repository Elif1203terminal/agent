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
