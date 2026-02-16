"""Claude API client for code generation."""

import os
import re

import anthropic

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 16384


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

    Handles multiple formats Claude may use:
        ```filename.py           (filepath as language tag)
        ```python filename.py    (language then filepath)
        ```python                (language tag, filename in first comment line)
        # filename.py
        ...
        ```

    Returns list of (relative_path, content) tuples.
    """
    files = []
    pattern = re.compile(
        r"```(\S+?)(?:[ \t]+(\S+?))?\n(.*?)```",
        re.DOTALL,
    )

    # Pattern to detect a filepath in a comment on the first line
    comment_path_re = re.compile(
        r"^(?:#|//|/\*|<!--)\s*(.+?\.\w+)\s*(?:\*/|-->)?\s*\n",
    )

    for match in pattern.finditer(response):
        tag = match.group(1)        # e.g. "app.py" or "python" or "css"
        second = match.group(2)     # e.g. "app.py" after "python" (if present)
        content = match.group(3)

        # Determine filename
        filename = None

        # Case 1: tag itself is a filepath (contains . and /)
        if "/" in tag and "." in tag:
            filename = tag
        # Case 2: second token is a filepath (```python app.py)
        elif second and "." in second:
            filename = second
        # Case 3: tag is a bare filename with extension (```style.css)
        elif "." in tag and "/" not in tag:
            filename = tag
        # Case 4: tag is just a language, check first line for a filepath comment
        else:
            cm = comment_path_re.match(content)
            if cm:
                filename = cm.group(1).strip()
                # Remove the comment line from content
                content = content[cm.end():]

        if not filename:
            continue

        # Strip a single trailing newline if present
        if content.endswith("\n"):
            content = content[:-1]

        files.append((filename, content))
    return files
