"""CLI Agent - generates command-line tools."""

import re
from agents.base import BaseAgent
from utils.template_engine import render_template


class CliAgent(BaseAgent):
    name = "cli"
    description = "Generates CLI tools using argparse or click"
    category = "cli"

    def _extract_tool_info(self, request):
        """Extract tool name and purpose from the request."""
        lower = request.lower()
        # Remove common prefixes
        for prefix in ("build a ", "create a ", "make a ", "generate a "):
            if lower.startswith(prefix):
                lower = lower[len(prefix):]
        # Remove "cli tool", "command line tool" etc.
        for suffix in (" cli tool", " cli", " command-line tool", " command line tool", " tool"):
            if lower.endswith(suffix):
                lower = lower[:-len(suffix)]

        # Try to extract main verb for default command
        words = lower.strip().split()
        command = words[0] if words else "run"
        description = lower.strip().capitalize() or "CLI tool"

        return command, description

    def generate(self, request, output_dir):
        command, desc = self._extract_tool_info(request)
        files = []

        # Use argparse template (stdlib, zero deps)
        content = render_template("cli", "argparse_cli.py.tpl", {
            "description": desc,
            "prog_name": re.sub(r"\s+", "_", desc.lower()),
            "default_command": command,
            "command_help": f"Run the {command} operation",
            "command_body": (
                f'print(f"Running {command} on: {{args.input}}")\n'
                f'    if args.verbose:\n'
                f'        print("Verbose mode enabled")\n'
                f'    if args.output:\n'
                f'        print(f"Output: {{args.output}}")\n'
                f'    # Add your logic here'
            ),
            "input_type": "file or directory",
        })
        files.append(self.write_file(output_dir, "main.py", content))

        return files

    def plan(self, request):
        command, desc = self._extract_tool_info(request)
        return [
            f"[cli] Generate argparse CLI tool: {desc}",
            f"[cli] Create main.py with '{command}' subcommand",
        ]
