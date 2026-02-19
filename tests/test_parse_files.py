"""Tests for utils.llm.parse_files — covers all four code block formats."""

from utils.llm import parse_files


# --- Case 1: tag is a filepath (contains both . and /) ---

def test_case1_path_as_tag():
    response = "```templates/index.html\n<h1>Hello</h1>\n```"
    result = parse_files(response)
    assert result == [("templates/index.html", "<h1>Hello</h1>")]


def test_case1_nested_path():
    response = "```static/css/style.css\nbody { margin: 0; }\n```"
    result = parse_files(response)
    assert result == [("static/css/style.css", "body { margin: 0; }")]


# --- Case 2: language tag then filepath (```python app.py) ---

def test_case2_language_then_filename():
    response = "```python app.py\nprint('hello')\n```"
    result = parse_files(response)
    assert result == [("app.py", "print('hello')")]


def test_case2_language_then_nested_path():
    response = "```javascript static/app.js\nconsole.log('hi');\n```"
    result = parse_files(response)
    assert result == [("static/app.js", "console.log('hi');")]


# --- Case 3: tag is a bare filename with extension (```style.css) ---

def test_case3_bare_filename():
    response = "```app.py\nprint('hello')\n```"
    result = parse_files(response)
    assert result == [("app.py", "print('hello')")]


def test_case3_bare_filename_css():
    response = "```style.css\nbody { color: red; }\n```"
    result = parse_files(response)
    assert result == [("style.css", "body { color: red; }")]


# --- Case 4: language tag, filename in first-line comment ---

def test_case4_python_hash_comment():
    response = "```python\n# main.py\nprint('hello')\n```"
    result = parse_files(response)
    assert result == [("main.py", "print('hello')")]


def test_case4_js_slash_comment():
    response = "```javascript\n// app.js\nconsole.log('hi');\n```"
    result = parse_files(response)
    assert result == [("app.js", "console.log('hi');")]


def test_case4_html_comment():
    response = "```html\n<!-- index.html -->\n<h1>Hi</h1>\n```"
    result = parse_files(response)
    assert result == [("index.html", "<h1>Hi</h1>")]


def test_case4_c_block_comment():
    response = "```c\n/* main.c */\nint main() {}\n```"
    result = parse_files(response)
    assert result == [("main.c", "int main() {}")]


def test_case4_comment_line_stripped_from_content():
    """The comment line with the filename must not appear in the output content."""
    response = "```python\n# script.py\nx = 1\ny = 2\n```"
    result = parse_files(response)
    assert len(result) == 1
    path, content = result[0]
    assert path == "script.py"
    assert "# script.py" not in content
    assert "x = 1" in content


# --- No filename → skipped ---

def test_no_filename_skipped():
    """Blocks with no detectable filename are silently skipped."""
    response = "```python\nprint('hello')\n```"
    result = parse_files(response)
    assert result == []


def test_plain_language_tag_no_comment_skipped():
    response = "```bash\necho hello\n```"
    result = parse_files(response)
    assert result == []


# --- Multiple files in one response ---

def test_multiple_files():
    response = (
        "```app.py\nprint('hello')\n```\n"
        "```python routes.py\nfrom flask import Flask\n```"
    )
    result = parse_files(response)
    assert len(result) == 2
    assert result[0] == ("app.py", "print('hello')")
    assert result[1] == ("routes.py", "from flask import Flask")


def test_mixed_formats_in_one_response():
    response = (
        "```templates/base.html\n<html></html>\n```\n"
        "```python\n# app.py\nfrom flask import Flask\n```\n"
        "```python run.py\napp.run()\n```"
    )
    result = parse_files(response)
    assert len(result) == 3
    assert result[0][0] == "templates/base.html"
    assert result[1][0] == "app.py"
    assert result[2][0] == "run.py"


# --- Trailing newline stripping ---

def test_trailing_newline_stripped():
    response = "```app.py\nprint('hi')\n```"
    _, content = parse_files(response)[0]
    assert not content.endswith("\n")


def test_no_extra_stripping_of_internal_newlines():
    response = "```app.py\nline1\nline2\nline3\n```"
    _, content = parse_files(response)[0]
    assert content == "line1\nline2\nline3"


# --- Empty response ---

def test_empty_response():
    assert parse_files("") == []


def test_no_code_blocks():
    assert parse_files("Here is some prose without any code blocks.") == []
