"""Template engine using string.Template for safe rendering."""

import os
from string import Template


def get_templates_dir():
    """Return the absolute path to the templates directory."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def load_template(category, template_name):
    """Load a template file and return its contents as a string."""
    templates_dir = get_templates_dir()
    path = os.path.join(templates_dir, category, template_name)
    resolved = os.path.realpath(path)
    if not resolved.startswith(os.path.realpath(templates_dir) + os.sep):
        raise ValueError(f"Template path escapes templates directory: {category}/{template_name}")
    with open(resolved, "r") as f:
        return f.read()


def render_template(category, template_name, variables):
    """Load and render a template with the given variables.

    Uses string.Template for safe substitution - unknown placeholders
    are left as-is rather than raising errors.
    """
    raw = load_template(category, template_name)
    tmpl = Template(raw)
    return tmpl.safe_substitute(variables)
