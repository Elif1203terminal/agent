"""Tests for DB/input/logging/file-access security patterns."""

from agents.security import SecurityAgent
from core.state import PipelineState, FileEntry


def _run(files: dict) -> list:
    agent = SecurityAgent()
    state = PipelineState(request="test", category="web", stack="flask")
    state.current_files = [
        FileEntry(path=path, content=content,
                  language="python" if path.endswith(".py") else "html")
        for path, content in files.items()
    ]
    state = agent.run(state)
    return state._security_issues


def _msgs(files):
    return [i.message for i in _run(files)]


def _sevs(files):
    return {i.message: i.severity for i in _run(files)}


# ---------------------------------------------------------------------------
# Raw cursor SQL
# ---------------------------------------------------------------------------

class TestRawCursor:
    def test_cursor_execute_flagged(self):
        msgs = _msgs({"app.py": 'cursor.execute("SELECT * FROM users")'})
        assert any("cursor" in m.lower() or "ORM" in m for m in msgs)

    def test_cursor_executemany_flagged(self):
        msgs = _msgs({"app.py": "cursor.executemany('INSERT INTO logs VALUES (?)', rows)"})
        assert any("cursor" in m.lower() or "ORM" in m for m in msgs)

    def test_severity_is_warning(self):
        sevs = _sevs({"app.py": 'cursor.execute("SELECT 1")'})
        assert any(s == "warning" for m, s in sevs.items() if "cursor" in m.lower() or "ORM" in m)

    def test_sqlalchemy_session_query_clean(self):
        msgs = _msgs({"app.py": "users = db.session.query(User).filter_by(active=True).all()"})
        sql_msgs = [m for m in msgs if "cursor" in m.lower()]
        assert len(sql_msgs) == 0


# ---------------------------------------------------------------------------
# Raw engine/connection execute
# ---------------------------------------------------------------------------

class TestRawEngineExecute:
    def test_engine_execute_flagged(self):
        msgs = _msgs({"app.py": 'db.engine.execute("SELECT count(*) FROM users")'})
        assert any("engine" in m.lower() or "ORM" in m for m in msgs)

    def test_connection_execute_flagged(self):
        msgs = _msgs({"app.py": 'connection.execute("DROP TABLE temp")'})
        assert any("connection" in m.lower() or "ORM" in m for m in msgs)

    def test_severity_is_warning(self):
        sevs = _sevs({"app.py": 'engine.execute("SELECT 1")'})
        assert any(s == "warning" for m, s in sevs.items() if "engine" in m.lower() or "ORM" in m)


# ---------------------------------------------------------------------------
# hashlib.sha256 for passwords
# ---------------------------------------------------------------------------

class TestHashlibSha256:
    def test_sha256_flagged(self):
        msgs = _msgs({"app.py": "hashed = hashlib.sha256(password.encode()).hexdigest()"})
        assert any("SHA-256" in m or "sha256" in m.lower() for m in msgs)

    def test_severity_is_warning(self):
        sevs = _sevs({"app.py": "hashlib.sha256(pw)"})
        assert any(s == "warning" for m, s in sevs.items() if "SHA" in m or "sha" in m.lower())

    def test_passlib_bcrypt_clean(self):
        msgs = _msgs({"app.py": "from passlib.hash import bcrypt\nhash = bcrypt.hash(password)"})
        sha_msgs = [m for m in msgs if "SHA-256" in m]
        assert len(sha_msgs) == 0


# ---------------------------------------------------------------------------
# FastAPI bypassing Pydantic
# ---------------------------------------------------------------------------

class TestFastAPIRawBody:
    def test_await_request_json_flagged(self):
        msgs = _msgs({"app.py": "    data = await request.json()"})
        assert any("Pydantic" in m or "raw request" in m.lower() for m in msgs)

    def test_await_request_body_flagged(self):
        msgs = _msgs({"app.py": "    raw = await request.body()"})
        assert any("Pydantic" in m or "raw request" in m.lower() for m in msgs)

    def test_severity_is_error(self):
        sevs = _sevs({"app.py": "data = await request.json()"})
        assert any(s == "error" for m, s in sevs.items() if "Pydantic" in m)

    def test_pydantic_model_param_clean(self):
        code = "async def create_user(user: UserCreate):\n    return user"
        msgs = _msgs({"app.py": code})
        pydantic_msgs = [m for m in msgs if "Pydantic" in m]
        assert len(pydantic_msgs) == 0


# ---------------------------------------------------------------------------
# Logging sensitive fields
# ---------------------------------------------------------------------------

class TestLoggingSensitiveFields:
    def test_logging_password_flagged(self):
        msgs = _msgs({"app.py": 'logger.info(f"Login: user={user} password={password}")'})
        assert any("log" in m.lower() and "sensitive" in m.lower() for m in msgs)

    def test_logging_token_flagged(self):
        msgs = _msgs({"app.py": 'logging.debug(f"Generated token={token}")'})
        assert any("log" in m.lower() and "sensitive" in m.lower() for m in msgs)

    def test_logging_secret_flagged(self):
        msgs = _msgs({"app.py": 'logger.error(f"Auth failed, secret={secret}")'})
        assert any("sensitive" in m.lower() for m in msgs)

    def test_logging_api_key_flagged(self):
        msgs = _msgs({"app.py": 'logger.warning(f"Using api_key={api_key}")'})
        assert any("sensitive" in m.lower() for m in msgs)

    def test_severity_is_error(self):
        sevs = _sevs({"app.py": 'logger.info(f"pw={password}")'})
        assert any(s == "error" for m, s in sevs.items() if "sensitive" in m.lower())

    def test_safe_logging_clean(self):
        msgs = _msgs({"app.py": 'logger.info(f"User {user_id} logged in successfully")'})
        log_sensitive = [m for m in msgs if "sensitive" in m.lower()]
        assert len(log_sensitive) == 0

    def test_logging_without_sensitive_clean(self):
        msgs = _msgs({"app.py": 'logging.info("Server started on port 5000")'})
        log_sensitive = [m for m in msgs if "sensitive" in m.lower()]
        assert len(log_sensitive) == 0


# ---------------------------------------------------------------------------
# Print sensitive fields
# ---------------------------------------------------------------------------

class TestPrintSensitiveFields:
    def test_print_password_flagged(self):
        msgs = _msgs({"app.py": 'print(f"Debug: password={password}")'})
        assert any("print" in m.lower() and "sensitive" in m.lower() for m in msgs)

    def test_print_token_flagged(self):
        msgs = _msgs({"app.py": 'print(f"token: {token}")'})
        assert any("sensitive" in m.lower() for m in msgs)

    def test_severity_is_warning(self):
        sevs = _sevs({"app.py": 'print(f"secret={secret}")'})
        assert any(s == "warning" for m, s in sevs.items() if "sensitive" in m.lower())

    def test_safe_print_clean(self):
        msgs = _msgs({"app.py": 'print(f"Processing user_id={user_id}")'})
        sensitive_msgs = [m for m in msgs if "sensitive" in m.lower() and "print" in m.lower()]
        assert len(sensitive_msgs) == 0


# ---------------------------------------------------------------------------
# Path traversal — open() with request data
# ---------------------------------------------------------------------------

class TestOpenPathTraversal:
    def test_open_request_args_flagged(self):
        msgs = _msgs({"app.py": "with open(request.args.get('file')) as f:"})
        assert any("traversal" in m.lower() or "path" in m.lower() for m in msgs)

    def test_open_request_form_flagged(self):
        msgs = _msgs({"app.py": "data = open(request.form['filename']).read()"})
        assert any("traversal" in m.lower() or "path" in m.lower() for m in msgs)

    def test_severity_is_error(self):
        sevs = _sevs({"app.py": "f = open(request.args['path'])"})
        assert any(s == "error" for m, s in sevs.items() if "traversal" in m.lower() or "path" in m.lower())

    def test_safe_open_clean(self):
        code = "with open('/var/app/data/report.txt') as f:\n    content = f.read()"
        msgs = _msgs({"app.py": code})
        traversal_msgs = [m for m in msgs if "traversal" in m.lower()]
        assert len(traversal_msgs) == 0


# ---------------------------------------------------------------------------
# Path traversal — send_file() with request data
# ---------------------------------------------------------------------------

class TestSendFilePathTraversal:
    def test_send_file_request_args_flagged(self):
        msgs = _msgs({"app.py": "return send_file(request.args.get('path'))"})
        assert any("traversal" in m.lower() or "send_file" in m.lower() for m in msgs)

    def test_send_file_request_form_flagged(self):
        msgs = _msgs({"app.py": "return send_file(request.form['filename'])"})
        assert any("traversal" in m.lower() or "send_file" in m.lower() for m in msgs)

    def test_severity_is_error(self):
        sevs = _sevs({"app.py": "send_file(request.json['file'])"})
        assert any(s == "error" for m, s in sevs.items() if "traversal" in m.lower() or "send_file" in m.lower())

    def test_send_from_directory_clean(self):
        code = "return send_from_directory(BASE_DIR, filename)"
        msgs = _msgs({"app.py": code})
        traversal_msgs = [m for m in msgs if "traversal" in m.lower()]
        assert len(traversal_msgs) == 0
