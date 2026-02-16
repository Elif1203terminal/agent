"""Folder naming utilities: slug generation, category dirs, dedup."""

import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

CATEGORY_DIRS = {
    "web": "web_apps",
    "api": "apis",
    "data": "data_scripts",
    "cli": "cli_tools",
    "script": "scripts",
}


def slugify(text):
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


def extract_project_name(request):
    """Pull a short project name from the request text."""
    # Remove common filler words to get the core noun
    filler = {
        "build", "me", "a", "an", "the", "create", "make", "generate",
        "write", "for", "to", "with", "using", "that", "and", "app",
        "application", "tool", "script", "program", "please", "can",
        "you", "i", "want", "need", "some", "new",
    }
    words = re.sub(r"[^\w\s]", "", request.lower()).split()
    meaningful = [w for w in words if w not in filler]
    name = "_".join(meaningful[:3]) if meaningful else "project"
    return slugify(name)


MAX_DEDUP = 1000


def _check_containment(path):
    """Verify the resolved path stays within BASE_DIR."""
    resolved = os.path.realpath(path)
    if not resolved.startswith(os.path.realpath(BASE_DIR) + os.sep):
        raise ValueError(f"Generated output path escapes base directory: {path}")
    return resolved


def get_output_dir(category, request):
    """Return a deduplicated output directory path for the given category and request."""
    category_dir = CATEGORY_DIRS.get(category, "scripts")
    project_name = extract_project_name(request)
    base = os.path.join(BASE_DIR, category_dir, project_name)
    _check_containment(base)

    if not os.path.exists(base):
        return base

    # Dedup with _2, _3, etc.
    for counter in range(2, MAX_DEDUP + 2):
        candidate = f"{base}_{counter}"
        if not os.path.exists(candidate):
            return candidate

    raise RuntimeError(f"Too many duplicate projects (>{MAX_DEDUP}) for: {project_name}")
