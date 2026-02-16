"""Script Agent - generates Python scripts using Claude."""

from agents.base import BaseAgent


class ScriptAgent(BaseAgent):
    name = "script"
    description = "Generates Python scripts for automation and file processing"
    category = "script"

    system_prompt = """You are a code generation agent that creates Python automation scripts.

When the user describes what they want, generate a complete, working script.

RULES:
- Use Python stdlib only — no pip dependencies unless truly necessary
- Generate at minimum: main.py
- The script should do something real and useful based on the user's description
- Include proper error handling (file not found, permissions, etc.)
- Include a clear usage message if command-line arguments are expected
- Use if __name__ == "__main__" pattern
- The script should be runnable with `python main.py`
- Only add requirements.txt if non-stdlib packages are used

OUTPUT FORMAT:
Return each file as a fenced code block with the filepath as the language tag:

```main.py
...
```

Only output the code blocks. No explanations."""

    def generate(self, request, output_dir):
        return self._generate_with_llm(request, output_dir)

    def plan(self, request):
        return [
            f"[script] Ask Claude to design a script for: {request}",
            "[script] Generate main.py",
        ]
