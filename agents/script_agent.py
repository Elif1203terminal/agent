"""Script Agent - generates Python scripts and automation."""

import re
from agents.base import BaseAgent
from utils.template_engine import render_template


def _safe_str(value):
    """Escape a value for safe embedding in generated Python source."""
    return repr(str(value))


class ScriptAgent(BaseAgent):
    name = "script"
    description = "Generates Python scripts for automation and file processing"
    category = "script"

    def _detect_type(self, request):
        """Detect which script template to use."""
        lower = request.lower()
        if any(w in lower for w in ("file", "rename", "move", "copy", "process", "convert")):
            return "file_processor"
        if any(w in lower for w in ("schedule", "cron", "interval", "periodic", "monitor")):
            return "scheduler"
        return "basic"

    def _extract_description(self, request):
        words = request.lower()
        for prefix in ("make a ", "create a ", "build a ", "write a ", "generate a ", "make a script to "):
            if words.startswith(prefix):
                words = words[len(prefix):]
        return words.strip().capitalize() or "Utility script"

    def generate(self, request, output_dir):
        script_type = self._detect_type(request)
        desc = self._extract_description(request)
        files = []

        if script_type == "file_processor":
            content = render_template("script", "file_processor.py.tpl", {
                "description": desc,
                "script_name": "main.py",
                "process_logic": (
                    'print(f"Processing: {filepath}")\n'
                    '    # Add your processing logic here'
                ),
            })
        elif script_type == "scheduler":
            content = render_template("script", "scheduler.py.tpl", {
                "description": desc,
                "task_body": 'print("Task executed.")',
                "interval": "60",
            })
        else:
            content = render_template("script", "basic_script.py.tpl", {
                "description": desc,
                "main_body": (
                    'print("Running: " + ' + _safe_str(desc) + ')\n'
                    '    # Add your logic here'
                ),
            })

        files.append(self.write_file(output_dir, "main.py", content))
        return files

    def plan(self, request):
        script_type = self._detect_type(request)
        desc = self._extract_description(request)
        return [
            f"[script] Generate {script_type} script: {desc}",
            f"[script] Create main.py",
        ]
