"""Claude API client for code generation."""

import os
import re

import anthropic

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 8192


def get_client():
    """Return an Anthropic client. Raises if no API key is set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Get a key at https://console.anthropic.com/ and run:\n"
            "  export ANTHROPIC_API_KEY='your-key-here'"
        )
    return anthropic.Anthropic(api_key=api_key)


def generate_code(system_prompt, user_request):
    """Call Claude and return the raw text response."""
    client = get_client()
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_request}],
    )
    return message.content[0].text


def parse_files(response):
    """Extract (filename, content) pairs from fenced code blocks.

    Expected format from Claude:
        ```filename.py
        code here
        ```

    Returns list of (relative_path, content) tuples.
    """
    files = []
    pattern = re.compile(
        r"```(\S+?)\n(.*?)```",
        re.DOTALL,
    )
    for match in pattern.finditer(response):
        filename = match.group(1)
        content = match.group(2)
        # Skip blocks that look like just a language tag (e.g. ```python)
        # A filename must contain a dot or slash
        if "." not in filename and "/" not in filename:
            continue
        # Strip a single trailing newline if present
        if content.endswith("\n"):
            content = content[:-1]
        files.append((filename, content))
    return files
