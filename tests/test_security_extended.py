"""Tests for extended security patterns and HTML/template scanning."""

import pytest
from agents.security import SecurityAgent
from core.state import PipelineState, FileEntry


def _run(files: dict) -> list:
    """Run SecurityAgent on a dict of {path: content} and return issues."""
    agent = SecurityAgent()
    state = PipelineState(request="test", category="web", stack="flask")
    state.current_files = [
        FileEntry(path=path, content=content, language="python" if path.endswith(".py") else "html")
        for path, content in files.items()
    ]
    state = agent.run(state)
    return state._security_issues


def _messages(files):
    return [i.message for i in _run(files)]


def _severities(files):
    return {i.message: i.severity for i in _run(files)}


# ---------------------------------------------------------------------------
# New Python patterns
# ---------------------------------------------------------------------------

class TestShellTrue:
    def test_detected(self):
        msgs = _messages({"app.py": "subprocess.run(['ls'], shell=True)"})
        assert any("shell=True" in m for m in msgs)

    def test_clean(self):
        msgs = _messages({"app.py": "subprocess.run(['ls', '-la'], shell=False)"})
        assert not any("shell=True" in m for m in msgs)

    def test_severity_is_error(self):
        sevs = _severities({"app.py": "subprocess.run(cmd, shell=True)"})
        assert any(s == "error" for m, s in sevs.items() if "shell=True" in m)


class TestWeakHashing:
    def test_md5_detected(self):
        msgs = _messages({"app.py": "hashlib.md5(password.encode()).hexdigest()"})
        assert any("MD5" in m or "SHA1" in m for m in msgs)

    def test_sha1_detected(self):
        msgs = _messages({"app.py": "hashlib.sha1(token.encode())"})
        assert any("MD5" in m or "SHA1" in m for m in msgs)

    def test_sha256_not_flagged(self):
        msgs = _messages({"app.py": "hashlib.sha256(data.encode())"})
        assert not any("MD5" in m or "SHA1" in m for m in msgs)

    def test_severity_is_error(self):
        sevs = _severities({"app.py": "hashlib.md5(pw)"})
        assert any(s == "error" for m, s in sevs.items() if "MD5" in m or "SHA1" in m)


class TestOpenRedirect:
    def test_detected_args(self):
        msgs = _messages({"app.py": "return redirect(request.args.get('next'))"})
        assert any("open redirect" in m.lower() for m in msgs)

    def test_detected_form(self):
        msgs = _messages({"app.py": "return redirect(request.form['url'])"})
        assert any("open redirect" in m.lower() for m in msgs)

    def test_safe_redirect(self):
        msgs = _messages({"app.py": "return redirect(url_for('index'))"})
        assert not any("open redirect" in m.lower() for m in msgs)


class TestSessionCookieConfig:
    def test_httponly_false_autofixed_dict_syntax(self):
        """Auto-fix replaces False with True in dict-style config — no issue reported."""
        agent = SecurityAgent()
        state = PipelineState(request="test", category="web", stack="flask")
        state.current_files = [
            FileEntry(path="app.py",
                      content="app.config['SESSION_COOKIE_HTTPONLY'] = False",
                      language="python")
        ]
        state = agent.run(state)
        assert "= True" in state.current_files[0].content
        assert "= False" not in state.current_files[0].content
        # Auto-fixed — should not appear as a remaining issue
        assert not any("HTTPONLY" in i.message for i in state._security_issues)

    def test_secure_false_detected(self):
        msgs = _messages({"app.py": "SESSION_COOKIE_SECURE = False"})
        assert any("SECURE" in m for m in msgs)

    def test_httponly_true_clean(self):
        msgs = _messages({"app.py": "app.config['SESSION_COOKIE_HTTPONLY'] = True"})
        assert not any("HTTPONLY" in m for m in msgs)


class TestSQLInjection:
    def test_format_method_detected(self):
        msgs = _messages({"app.py": "cursor.execute(\"SELECT * FROM users WHERE id='%s'\" .format(uid))"})
        assert any("format" in m.lower() or "SQL injection" in m for m in msgs)

    def test_concatenation_detected(self):
        msgs = _messages({"app.py": 'cursor.execute("SELECT * FROM u WHERE id=" + user_id)'})
        assert any("concatenation" in m.lower() or "SQL injection" in m for m in msgs)

    def test_parameterized_safe(self):
        msgs = _messages({"app.py": 'cursor.execute("SELECT * FROM u WHERE id=?", (user_id,))'})
        # No SQL injection issues for parameterized queries
        sql_msgs = [m for m in msgs if "SQL injection" in m]
        assert len(sql_msgs) == 0

    def test_fstring_still_caught(self):
        # Original pattern from before
        msgs = _messages({"app.py": 'cursor.execute(f"SELECT * FROM users WHERE id={uid}")'})
        assert any("SQL" in m for m in msgs)


class TestInsecureRandom:
    def test_import_random_flagged(self):
        msgs = _messages({"app.py": "import random\ntoken = random.randint(0, 9999)"})
        assert any("random" in m.lower() for m in msgs)

    def test_import_secrets_clean(self):
        msgs = _messages({"app.py": "import secrets\ntoken = secrets.token_urlsafe(32)"})
        assert not any("random module" in m.lower() for m in msgs)

    def test_severity_is_warning(self):
        sevs = _severities({"app.py": "import random"})
        assert any(s == "warning" for m, s in sevs.items() if "random" in m.lower())


# ---------------------------------------------------------------------------
# HTML/Template patterns
# ---------------------------------------------------------------------------

class TestXSSSafeFilter:
    def test_safe_filter_detected(self):
        msgs = _messages({"templates/index.html": "<p>{{ user_input | safe }}</p>"})
        assert any("safe" in m.lower() for m in msgs)

    def test_no_safe_filter_clean(self):
        msgs = _messages({"templates/index.html": "<p>{{ user_input }}</p>"})
        assert not any("| safe" in m for m in msgs)

    def test_severity_is_error(self):
        sevs = _severities({"templates/index.html": "{{ data | safe }}"})
        assert any(s == "error" for m, s in sevs.items() if "safe" in m.lower())


class TestMarkupUsage:
    def test_markup_detected(self):
        msgs = _messages({"templates/index.html": "{{ Markup(user_content) }}"})
        assert any("Markup" in m for m in msgs)

    def test_severity_is_warning(self):
        sevs = _severities({"templates/index.html": "{{ Markup(val) }}"})
        assert any(s == "warning" for m, s in sevs.items() if "Markup" in m)


class TestHTTPResources:
    def test_http_script_src_detected(self):
        msgs = _messages({"templates/index.html": '<script src="http://cdn.example.com/lib.js"></script>'})
        assert any("HTTP" in m or "HTTPS" in m for m in msgs)

    def test_https_script_src_clean(self):
        issues = _run({"templates/index.html": '<script src="https://cdn.example.com/lib.js"></script>'})
        http_issues = [i for i in issues if ("HTTP" in i.message or "HTTPS" in i.message) and i.severity == "error"]
        assert len(http_issues) == 0

    def test_http_href_detected(self):
        msgs = _messages({"templates/index.html": '<a href="http://example.com">link</a>'})
        assert any("HTTP" in m or "HTTPS" in m for m in msgs)


class TestJavascriptURI:
    def test_javascript_uri_detected(self):
        msgs = _messages({"templates/index.html": '<a href="javascript:void(0)">click</a>'})
        assert any("javascript:" in m.lower() or "XSS" in m for m in msgs)

    def test_severity_is_error(self):
        sevs = _severities({"templates/index.html": 'href="javascript:doThing()"'})
        assert any(s == "error" for m, s in sevs.items() if "javascript" in m.lower())


# ---------------------------------------------------------------------------
# CSRF whole-file check
# ---------------------------------------------------------------------------

class TestCSRFCheck:
    def test_post_form_no_csrf_flagged(self):
        html = '<form method="post"><input name="email"></form>'
        msgs = _messages({"templates/form.html": html})
        assert any("CSRF" in m for m in msgs)

    def test_post_form_with_csrf_token_clean(self):
        html = '<form method="post">{{ csrf_token() }}<input name="email"></form>'
        msgs = _messages({"templates/form.html": html})
        assert not any("CSRF" in m for m in msgs)

    def test_post_form_with_hidden_tag_clean(self):
        html = '<form method="post">{{ form.hidden_tag() }}<input name="email"></form>'
        msgs = _messages({"templates/form.html": html})
        assert not any("CSRF" in m for m in msgs)

    def test_get_form_not_flagged(self):
        html = '<form method="get"><input name="q"></form>'
        msgs = _messages({"templates/search.html": html})
        assert not any("CSRF" in m for m in msgs)

    def test_no_form_not_flagged(self):
        html = '<div><p>Hello world</p></div>'
        msgs = _messages({"templates/page.html": html})
        assert not any("CSRF" in m for m in msgs)

    def test_severity_is_error(self):
        html = '<form method="POST"><input name="x"></form>'
        issues = _run({"templates/form.html": html})
        csrf_issues = [i for i in issues if "CSRF" in i.message]
        assert len(csrf_issues) == 1
        assert csrf_issues[0].severity == "error"

    def test_post_case_insensitive(self):
        html = '<form METHOD="POST"><input name="x"></form>'
        msgs = _messages({"templates/form.html": html})
        assert any("CSRF" in m for m in msgs)


# ---------------------------------------------------------------------------
# HTML files are scanned, .py files use Python patterns only
# ---------------------------------------------------------------------------

class TestFileScopedScanning:
    def test_py_file_uses_python_patterns(self):
        # | safe is an HTML pattern — should NOT be flagged in a .py file
        msgs = _messages({"app.py": "result = value | safe_filter()"})
        safe_msgs = [m for m in msgs if "| safe" in m]
        assert len(safe_msgs) == 0

    def test_html_file_uses_html_patterns(self):
        # shell=True is a Python pattern — should NOT be flagged in an HTML file
        msgs = _messages({"templates/index.html": "<!-- shell=True comment -->"})
        shell_msgs = [m for m in msgs if "shell=True" in m]
        assert len(shell_msgs) == 0

    def test_jinja2_extension_scanned(self):
        content = "{{ user_data | safe }}"
        msgs = _messages({"templates/page.jinja2": content})
        assert any("safe" in m.lower() for m in msgs)
