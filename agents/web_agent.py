"""Web Agent - generates Flask web applications."""

import html
import os
from agents.base import BaseAgent
from utils.template_engine import render_template


class WebAgent(BaseAgent):
    name = "web"
    description = "Generates Flask web applications with HTML templates and CSS"
    category = "web"

    def _extract_app_name(self, request):
        """Extract a human-readable app name from the request."""
        words = request.lower()
        for prefix in ("build me a ", "build a ", "create a ", "make a ", "generate a "):
            if words.startswith(prefix):
                words = words[len(prefix):]
        # Remove trailing "web app", "app", etc.
        for suffix in (" web app", " webapp", " application", " app", " website", " site"):
            if words.endswith(suffix):
                words = words[:-len(suffix)]
        return words.strip().title() or "My App"

    def _is_dashboard(self, request):
        """Check if the request is for a dashboard/charts app."""
        lower = request.lower()
        keywords = ("dashboard", "chart", "visualization", "analytics", "metrics")
        return any(kw in lower for kw in keywords)

    def generate(self, request, output_dir):
        app_name = self._extract_app_name(request)
        safe_app_name = html.escape(app_name)
        files = []

        if self._is_dashboard(request):
            return self._generate_dashboard(app_name, safe_app_name, output_dir)

        # app.py
        content = render_template("web", "flask_app.py.tpl", {
            "app_name": app_name,
            "data_store": "items = []",
            "items_var": "items",
            "add_logic": "items.append(item)",
            "delete_logic": (
                "if 0 <= item_id < len(items):\n"
                "        items.pop(item_id)"
            ),
        })
        files.append(self.write_file(output_dir, "app.py", content))

        # templates/index.html
        content = render_template("web", "index_html.tpl", {
            "app_name": safe_app_name,
            "input_placeholder": "Add new item...",
        })
        files.append(self.write_file(output_dir, "templates/index.html", content))

        # static/style.css
        content = render_template("web", "style_css.tpl", {
            "primary_color": "#3498db",
        })
        files.append(self.write_file(output_dir, "static/style.css", content))

        # requirements.txt
        content = render_template("web", "requirements_txt.tpl", {})
        files.append(self.write_file(output_dir, "requirements.txt", content))

        return files

    def _generate_dashboard(self, app_name, safe_app_name, output_dir):
        """Generate a dashboard app with charts."""
        files = []

        content = render_template("web", "dashboard_app.py.tpl", {
            "app_name": app_name,
        })
        files.append(self.write_file(output_dir, "app.py", content))

        content = render_template("web", "dashboard_html.tpl", {
            "app_name": safe_app_name,
        })
        files.append(self.write_file(output_dir, "templates/dashboard.html", content))

        content = render_template("web", "dashboard_css.tpl", {
            "primary_color": "#3498db",
            "header_color": "#2c3e50",
        })
        files.append(self.write_file(output_dir, "static/style.css", content))

        content = render_template("web", "requirements_txt.tpl", {})
        files.append(self.write_file(output_dir, "requirements.txt", content))

        return files

    def plan(self, request):
        app_name = self._extract_app_name(request)
        if self._is_dashboard(request):
            return [
                f"[web] Create Flask dashboard: {app_name}",
                "[web] Generate app.py with routes (index, /api/data)",
                "[web] Generate templates/dashboard.html with Chart.js bar + doughnut charts",
                "[web] Generate static/style.css (dashboard layout)",
                "[web] Generate requirements.txt",
            ]
        return [
            f"[web] Create Flask app: {app_name}",
            "[web] Generate app.py with routes (index, add, delete)",
            "[web] Generate templates/index.html",
            "[web] Generate static/style.css",
            "[web] Generate requirements.txt",
        ]
