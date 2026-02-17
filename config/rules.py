"""Security and lint rule patterns per stack."""

import re

# Patterns that indicate security issues. Each entry:
# (pattern_regex, severity, message, suggestion, auto_fix_from, auto_fix_to)
# auto_fix_from/auto_fix_to: if both are set, the agent can fix this automatically
# via string replacement. Set both to None for issues that need manual/LLM fixes.
SECURITY_PATTERNS = [
    (
        re.compile(r"""(?:password|secret|api_key|token)\s*=\s*["'][^"']+["']""", re.IGNORECASE),
        "error",
        "Hardcoded secret or credential",
        "Use environment variables: os.environ.get('KEY_NAME')",
        None, None,
    ),
    (
        re.compile(r"""\bdebug\s*=\s*True\b""", re.IGNORECASE),
        "warning",
        "Debug mode enabled",
        "Set debug=False for production or use an environment variable",
        re.compile(r"""\bdebug\s*=\s*True\b""", re.IGNORECASE),
        "debug=False",
    ),
    (
        re.compile(r"""\beval\s*\("""),
        "error",
        "Use of eval() is unsafe",
        "Replace eval() with a safe alternative (ast.literal_eval, json.loads, etc.)",
        None, None,
    ),
    (
        re.compile(r"""\bexec\s*\("""),
        "error",
        "Use of exec() is unsafe",
        "Avoid exec(); use explicit function calls instead",
        None, None,
    ),
    (
        re.compile(r"""\bos\.system\s*\("""),
        "warning",
        "os.system() is vulnerable to shell injection",
        "Use subprocess.run() with a list of arguments instead",
        None, None,
    ),
    (
        re.compile(r"""["']0\.0\.0\.0["']"""),
        "warning",
        "Binding to 0.0.0.0 exposes service to all interfaces",
        "Bind to 127.0.0.1 for local development",
        re.compile(r"""(['"])0\.0\.0\.0\1"""),
        "'127.0.0.1'",
    ),
    (
        re.compile(r"""\bSECRET_KEY\s*=\s*["'][^"']+["']""", re.IGNORECASE),
        "error",
        "Hardcoded SECRET_KEY",
        "Use os.environ.get('SECRET_KEY') or generate at runtime with os.urandom()",
        None, None,
    ),
    (
        re.compile(r"""execute\s*\(\s*["'].*%s"""),
        "error",
        "Possible SQL injection via string formatting",
        "Use parameterized queries with ? or %s placeholders",
        None, None,
    ),
    (
        re.compile(r"""execute\s*\(\s*f["']"""),
        "error",
        "Possible SQL injection via f-string",
        "Use parameterized queries instead of f-strings in SQL",
        None, None,
    ),
    (
        re.compile(r"""\bpickle\.loads?\s*\("""),
        "warning",
        "pickle.load() can execute arbitrary code on untrusted data",
        "Use json.loads() or validate input source before unpickling",
        None, None,
    ),
]
