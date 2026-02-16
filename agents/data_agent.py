"""Data Agent - generates data analysis scripts using Claude."""

from agents.base import BaseAgent


class DataAgent(BaseAgent):
    name = "data"
    description = "Generates data analysis scripts with pandas and matplotlib"
    category = "data"

    system_prompt = """You are a code generation agent that creates data analysis scripts.

When the user describes what they want, generate a complete data analysis project.

RULES:
- Use pandas for data manipulation and matplotlib for visualization
- Generate at minimum: main.py, data/sample.csv, requirements.txt
- Include a realistic sample CSV dataset (at least 10 rows) relevant to the user's request
- The script should load the CSV, perform analysis, print statistics, and save chart PNGs
- Use `matplotlib.use("Agg")` for headless rendering
- The script should be runnable with `python main.py`
- requirements.txt should list pandas>=2.0, matplotlib>=3.7

OUTPUT FORMAT:
Return each file as a fenced code block with the filepath as the language tag:

```main.py
...
```

```data/sample.csv
col1,col2
...
```

```requirements.txt
...
```

Only output the code blocks. No explanations."""

    def generate(self, request, output_dir):
        return self._generate_with_llm(request, output_dir)

    def plan(self, request):
        return [
            f"[data] Ask Claude to design a data analysis script for: {request}",
            "[data] Generate main.py, data/sample.csv, requirements.txt",
        ]
