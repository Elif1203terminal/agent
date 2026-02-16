"""Data Agent - generates data analysis and CSV processing scripts."""

import os
from agents.base import BaseAgent
from utils.template_engine import render_template


class DataAgent(BaseAgent):
    name = "data"
    description = "Generates data analysis scripts with pandas and matplotlib"
    category = "data"

    def _detect_type(self, request):
        lower = request.lower()
        if any(w in lower for w in ("visuali", "chart", "plot", "graph")):
            return "visualizer"
        if any(w in lower for w in ("csv", "process", "clean", "transform")):
            return "csv_processor"
        return "analysis"

    def _extract_description(self, request):
        words = request.lower()
        for prefix in ("make a ", "create a ", "build a ", "write a ", "generate a "):
            if words.startswith(prefix):
                words = words[len(prefix):]
        return words.strip().capitalize() or "Data analysis"

    def generate(self, request, output_dir):
        script_type = self._detect_type(request)
        desc = self._extract_description(request)
        files = []

        if script_type == "visualizer":
            content = render_template("data", "data_visualizer.py.tpl", {
                "description": desc,
                "default_csv": "data/input.csv",
                "app_name": desc,
            })
        elif script_type == "csv_processor":
            content = render_template("data", "csv_processor.py.tpl", {
                "description": desc,
                "script_name": "main.py",
                "process_logic": (
                    "# Add processing logic here\n"
                    "    for row in rows:\n"
                    "        pass  # transform each row"
                ),
            })
        else:
            content = render_template("data", "pandas_analysis.py.tpl", {
                "description": desc,
                "default_csv": "data/input.csv",
            })

        files.append(self.write_file(output_dir, "main.py", content))

        # Create sample data directory
        os.makedirs(os.path.join(output_dir, "data"), exist_ok=True)

        sample_csv = "name,value,category\nAlpha,10,A\nBeta,25,B\nGamma,15,A\nDelta,30,B\nEpsilon,20,A\n"
        files.append(self.write_file(output_dir, "data/input.csv", sample_csv))

        # requirements.txt
        files.append(self.write_file(output_dir, "requirements.txt", "pandas>=2.0\nmatplotlib>=3.7\n"))

        return files

    def plan(self, request):
        script_type = self._detect_type(request)
        desc = self._extract_description(request)
        return [
            f"[data] Generate {script_type} script: {desc}",
            "[data] Create main.py",
            "[data] Create data/ directory with sample CSV",
            "[data] Generate requirements.txt",
        ]
