"""Keyword-scoring request classifier."""

import re

# Keywords that are prefix patterns (match word starts, e.g. "automat" -> "automation")
_PREFIX_KEYWORDS = {"automat", "visuali"}

KEYWORDS = {
    "web": {
        "web": 3, "website": 3, "html": 3, "flask": 4, "frontend": 3,
        "page": 2, "dashboard": 3, "template": 1, "css": 2, "static": 1,
        "form": 1, "ui": 2, "webapp": 4, "jinja": 2, "bootstrap": 2,
    },
    "api": {
        "api": 4, "rest": 4, "endpoint": 3, "fastapi": 4, "crud": 3,
        "json": 2, "resource": 2, "route": 2, "http": 2, "microservice": 3,
        "backend": 2, "server": 1, "post": 1, "get": 1,
    },
    "data": {
        "data": 3, "csv": 4, "pandas": 4, "analysis": 3, "visuali": 3,
        "chart": 3, "plot": 3, "dataset": 3, "dataframe": 4, "excel": 3,
        "statistics": 3, "graph": 2, "report": 2, "matplotlib": 4,
    },
    "cli": {
        "cli": 4, "command": 3, "argparse": 4, "click": 4, "terminal": 3,
        "flag": 2, "argument": 2, "subcommand": 3, "option": 1,
        "command-line": 4, "interactive": 1,
    },
    "script": {
        "script": 3, "automat": 3, "file": 2, "rename": 2, "backup": 3,
        "batch": 2, "cron": 3, "schedule": 3, "process": 2, "convert": 2,
        "download": 2, "utility": 2, "helper": 2, "clean": 1, "monitor": 2,
    },
}


def classify(request):
    """Score a request against each category and return the best match.

    Returns (category, scores_dict).
    """
    text = request.lower()
    scores = {}
    for category, kw_map in KEYWORDS.items():
        score = 0
        for keyword, weight in kw_map.items():
            if keyword in _PREFIX_KEYWORDS:
                pattern = r'\b' + re.escape(keyword)
            else:
                pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text):
                score += weight
        scores[category] = score

    best = max(scores, key=scores.get)
    # Default to 'script' if nothing scored
    if scores[best] == 0:
        best = "script"
    return best, scores
