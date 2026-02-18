"""Default pipeline settings."""

DEFAULTS = {
    "max_iterations": 2,
    "hard_max_iterations": 5,   # absolute ceiling, cannot be overridden
    "model": "claude-sonnet-4-5-20250929",
    "max_tokens": 32768,
    "sandbox_timeout": 30,
    "allowed_commands": ["python3", "pip", "flake8", "pytest", "black"],
}
