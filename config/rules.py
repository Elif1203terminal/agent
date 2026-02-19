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
    (
        re.compile(r"""\bshell\s*=\s*True\b"""),
        "error",
        "shell=True in subprocess is vulnerable to command injection",
        "Use shell=False and pass arguments as a list: subprocess.run(['cmd', 'arg'])",
        None, None,
    ),
    (
        re.compile(r"""\bhashlib\.(md5|sha1)\s*\("""),
        "error",
        "MD5/SHA1 are cryptographically broken — never use for passwords or security tokens",
        "Use bcrypt or werkzeug.security.generate_password_hash() for passwords",
        None, None,
    ),
    (
        re.compile(r"""\bredirect\s*\(\s*request\.(args|form|values|json)\b"""),
        "error",
        "Potential open redirect — redirect destination is user-controlled",
        "Validate the URL against an allowlist before redirecting",
        None, None,
    ),
    (
        re.compile(r"""SESSION_COOKIE_HTTPONLY['"]\s*\]\s*=\s*False\b|(?<!\[)SESSION_COOKIE_HTTPONLY\s*=\s*False\b""", re.IGNORECASE),
        "error",
        "SESSION_COOKIE_HTTPONLY=False allows JavaScript to read the session cookie (XSS risk)",
        "Set SESSION_COOKIE_HTTPONLY=True",
        re.compile(r"""(SESSION_COOKIE_HTTPONLY['"]\s*\]\s*=\s*)False\b""", re.IGNORECASE),
        r"\g<1>True",
    ),
    (
        re.compile(r"""SESSION_COOKIE_SECURE['"]\s*\]\s*=\s*False\b|(?<!\[)SESSION_COOKIE_SECURE\s*=\s*False\b""", re.IGNORECASE),
        "warning",
        "SESSION_COOKIE_SECURE=False sends session cookies over plain HTTP",
        "Set SESSION_COOKIE_SECURE=True for any internet-facing deployment",
        None, None,
    ),
    (
        re.compile(r"""execute\s*\(\s*["'].*["']\s*\.format\s*\("""),
        "error",
        "SQL injection risk — .format() used to build a query string",
        "Use parameterized queries: cursor.execute('SELECT ... WHERE id=?', (val,))",
        None, None,
    ),
    (
        re.compile(r"""execute\s*\([^)]*["']\s*\+"""),
        "error",
        "SQL injection risk — string concatenation used to build a query",
        "Use parameterized queries: cursor.execute('SELECT ... WHERE id=?', (val,))",
        None, None,
    ),
    (
        re.compile(r"""\bimport\s+random\b"""),
        "warning",
        "random module is not cryptographically secure — do not use for tokens, keys, or passwords",
        "Use the secrets module for security-sensitive random values: secrets.token_urlsafe(32)",
        None, None,
    ),

    # --- Database ---
    (
        re.compile(r"""\bcursor\.(execute|executemany)\s*\("""),
        "warning",
        "Raw SQL cursor used — prefer SQLAlchemy ORM to eliminate injection risk and improve safety",
        "Use SQLAlchemy ORM: db.session.query(Model).filter_by(...) or Model.query.all()",
        None, None,
    ),
    (
        re.compile(r"""\b(?:db\.engine|engine|connection)\.execute\s*\("""),
        "warning",
        "Raw SQLAlchemy engine/connection execute bypasses ORM safety — use session queries instead",
        "Use db.session.execute() with text() and bound parameters, or use ORM model queries",
        None, None,
    ),
    (
        re.compile(r"""\bhashlib\.sha256\s*\("""),
        "warning",
        "SHA-256 alone is not safe for password hashing (no salt, no iterations)",
        "Use passlib with bcrypt or argon2: from passlib.hash import bcrypt; bcrypt.hash(password)",
        None, None,
    ),

    # --- FastAPI input validation ---
    (
        re.compile(r"""await\s+request\.(json|body)\s*\(\)"""),
        "error",
        "FastAPI: reading raw request body bypasses Pydantic validation",
        "Define a Pydantic BaseModel and declare it as a route parameter — FastAPI validates automatically",
        None, None,
    ),

    # --- Sensitive data in logs/output ---
    (
        re.compile(
            r"""(?:logging|logger)\s*\.\s*(?:debug|info|warning|error|critical)\s*\("""
            r""".*\b(?:password|passwd|secret|token|api_key|credit_card|ssn|cvv)\b""",
            re.IGNORECASE,
        ),
        "error",
        "Sensitive field being written to logs — will be exposed in log files and monitoring systems",
        "Remove sensitive fields from log statements; log only non-sensitive identifiers (e.g. user_id)",
        None, None,
    ),
    (
        re.compile(
            r"""\bprint\s*\(.*\b(?:password|passwd|secret|api_key|token)\b""",
            re.IGNORECASE,
        ),
        "warning",
        "Sensitive field in print() statement — remove before production",
        "Remove debug print statements that include passwords, secrets, or tokens",
        None, None,
    ),

    # --- HTTPS enforcement ---
    (
        re.compile(r"""app\.run\s*\((?!.*ssl_context)"""),
        "warning",
        "Flask app.run() without ssl_context — traffic is unencrypted in development",
        "Add ssl_context='adhoc' for dev HTTPS, or deploy behind a TLS-terminating proxy in production",
        None, None,
    ),

    # --- Path traversal ---
    (
        re.compile(r"""\bopen\s*\(\s*request\.(args|form|values|json|files)""", re.IGNORECASE),
        "error",
        "Path traversal risk — open() called with user-supplied path",
        "Resolve and validate the path: safe = os.path.realpath(path); assert safe.startswith(BASE_DIR)",
        None, None,
    ),
    (
        re.compile(r"""\bsend_file\s*\(\s*request\.(args|form|values|json)""", re.IGNORECASE),
        "error",
        "Path traversal risk — send_file() called with user-supplied path",
        "Use send_from_directory(BASE_DIR, filename) with a validated filename instead",
        None, None,
    ),
]

# Patterns applied to HTML/Jinja2 template files (.html, .jinja2, .j2)
# Each entry: (pattern_regex, severity, message, suggestion, auto_fix_from, auto_fix_to)
HTML_SECURITY_PATTERNS = [
    (
        re.compile(r"""\|\s*safe\b"""),
        "error",
        "Jinja2 '| safe' disables auto-escaping — XSS risk if applied to any user-controlled value",
        "Remove '| safe' unless the value is 100% trusted server-side content",
        None, None,
    ),
    (
        re.compile(r"""\bMarkup\s*\("""),
        "warning",
        "Markup() marks content as safe HTML — only use on fully trusted, server-generated content",
        "Ensure this value is never derived from user input",
        None, None,
    ),
    (
        re.compile(r"""src\s*=\s*["']http://""", re.IGNORECASE),
        "error",
        "External resource loaded over HTTP (not HTTPS) — vulnerable to man-in-the-middle attack",
        "Use HTTPS for all external scripts, stylesheets, and resources",
        None, None,
    ),
    (
        re.compile(r"""href\s*=\s*["']http://""", re.IGNORECASE),
        "warning",
        "Link uses HTTP instead of HTTPS",
        "Use HTTPS for all external links and resources",
        None, None,
    ),
    (
        re.compile(r"""javascript\s*:""", re.IGNORECASE),
        "error",
        "javascript: URI is a common XSS vector",
        "Use event listeners (onclick, addEventListener) instead of javascript: URIs",
        None, None,
    ),
    (
        re.compile(r"""<\s*script[^>]+src\s*=\s*["'][^"']*["'][^>]*>""", re.IGNORECASE),
        "warning",
        "External script loaded without integrity attribute (Subresource Integrity)",
        "Add integrity='sha384-...' and crossorigin='anonymous' to external script tags",
        None, None,
    ),
]
