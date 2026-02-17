"""Stack definitions mapping category to technology config."""

STACKS = {
    "static": {
        "name": "Static Website",
        "category": "web",
        "expected_files": ["index.html", "style.css"],
        "run_command": [],
        "test_command": [],
        "lint_command": [],
    },
    "flask": {
        "name": "Flask Web App",
        "category": "web",
        "expected_files": ["app.py", "templates/index.html", "static/style.css", "requirements.txt"],
        "run_command": ["python3", "app.py"],
        "test_command": ["python3", "-c", "import app"],
        "lint_command": ["flake8", "--max-line-length=120", "app.py"],
    },
    "fastapi": {
        "name": "FastAPI REST API",
        "category": "api",
        "expected_files": ["app.py", "requirements.txt"],
        "run_command": ["uvicorn", "app:app", "--reload"],
        "test_command": ["python3", "-c", "import app"],
        "lint_command": ["flake8", "--max-line-length=120", "app.py"],
    },
    "cli": {
        "name": "CLI Tool",
        "category": "cli",
        "expected_files": ["main.py", "requirements.txt"],
        "run_command": ["python3", "main.py", "--help"],
        "test_command": ["python3", "-c", "import main"],
        "lint_command": ["flake8", "--max-line-length=120", "main.py"],
    },
    "data": {
        "name": "Data Analysis Script",
        "category": "data",
        "expected_files": ["main.py", "requirements.txt"],
        "run_command": ["python3", "main.py"],
        "test_command": ["python3", "-c", "import main"],
        "lint_command": ["flake8", "--max-line-length=120", "main.py"],
    },
    "script": {
        "name": "Python Script",
        "category": "script",
        "expected_files": ["main.py"],
        "run_command": ["python3", "main.py"],
        "test_command": ["python3", "-c", "import main"],
        "lint_command": ["flake8", "--max-line-length=120", "main.py"],
    },
}

# Map category names to default stack
CATEGORY_TO_STACK = {
    "web": "flask",
    "api": "fastapi",
    "cli": "cli",
    "data": "data",
    "script": "script",
}
