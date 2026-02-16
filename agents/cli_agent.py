"""CLI Agent - generates command-line tools using Claude."""

from agents.base import BaseAgent


class CliAgent(BaseAgent):
    name = "cli"
    description = "Generates CLI tools using argparse or click"
    category = "cli"

    system_prompt = """You are a code generation agent that creates command-line tools.

When the user describes what they want, generate a complete CLI tool.

RULES:
- Use argparse (stdlib) by default — no extra dependencies needed
- Generate at minimum: main.py
- Include subcommands if the tool has multiple operations
- Include --help text for all arguments and subcommands
- Include --verbose flag where appropriate
- The tool should do something real and useful, not just print placeholders
- The script should be runnable with `python main.py <args>`
- Only add requirements.txt if non-stdlib packages are needed

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
            f"[cli] Ask Claude to design a CLI tool for: {request}",
            "[cli] Generate main.py",
        ]
