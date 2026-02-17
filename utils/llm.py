"""Claude API client for code generation."""

import json
import os
import re
import time

import anthropic

from config.defaults import DEFAULTS

MODEL = DEFAULTS["model"]
MAX_TOKENS = DEFAULTS["max_tokens"]


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
    """Call Claude and return the raw text response. (Backward compat.)"""
    return call_llm(system_prompt, user_request)


def call_llm(system_prompt, user_message, response_format=None):
    """Call Claude with optional structured JSON output.

    Args:
        system_prompt: System prompt string.
        user_message: User message string.
        response_format: If "json", appends instruction to return valid JSON
                         and attempts to parse the response.

    Returns:
        Raw text string, or parsed dict/list if response_format="json".
    """
    client = get_client()

    if response_format == "json":
        system_prompt = system_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown fences, no commentary."

    last_error = None
    for attempt in range(2):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text = message.content[0].text

            if response_format == "json":
                # Strip markdown fences if model included them anyway
                cleaned = text.strip()
                if cleaned.startswith("```"):
                    cleaned = re.sub(r"^```\w*\n?", "", cleaned)
                    cleaned = re.sub(r"\n?```$", "", cleaned)
                return json.loads(cleaned)

            return text

        except anthropic.APIError as e:
            last_error = e
            if attempt == 0:
                time.sleep(2)
                continue
            raise
        except json.JSONDecodeError:
            # Return raw text if JSON parsing fails
            return text

    raise last_error


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
