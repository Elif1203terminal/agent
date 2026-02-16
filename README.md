# AgentsOne

A multi-agent code generation system. Describe what you want in plain English and it generates a ready-to-go project folder with all the code files.

A manager agent classifies your request via keyword scoring and delegates to one of 5 specialist agents, which select a template, fill in the variables, and write the files to disk.

Zero external dependencies -- runs on Python 3 stdlib only.

## Getting Started

```bash
cd /home/lee/agentsone
python3 main.py "build me a todo web app"
```

That's it. Nothing to install.

## What Can You Ask For?

| Say something like... | What you get |
|---|---|
| `"build me a todo web app"` | A Flask website with HTML, CSS, and routes |
| `"create a REST API for users"` | A FastAPI app with full CRUD endpoints and models |
| `"make a CSV data analysis script"` | A pandas script with sample data and visualization support |
| `"build a CLI tool for file renaming"` | A command-line tool with argument parsing |
| `"make a script to backup my photos"` | A standalone Python automation script |

You don't need to be precise. It reads keywords in your request and picks the right agent. "I want a website that tracks my books" works just as well as "build a Flask web app".

## Options

Preview what would be created without writing any files:

```bash
python3 main.py --dry-run "build me a blog web app"
```

List all available agents:

```bash
python3 main.py --list-agents
```

## Running Generated Code

After generating, `cd` into the output folder. If the project has a `requirements.txt`, install dependencies first:

```bash
cd web_apps/todo_web
pip install -r requirements.txt
python3 app.py
```

For simpler scripts with no dependencies:

```bash
cd scripts/backup_my_photos
python3 main.py
```

## Output Structure

Generated projects are organized into category folders:

```
web_apps/todo_web/           # Flask app with templates/, static/
apis/rest_api_user/          # FastAPI CRUD with models.py
data_scripts/csv_analysis/   # pandas script with data/ dir
cli_tools/file_renamer/      # argparse-based CLI
scripts/backup_my_photos/    # utility script
```

Running the same request twice won't overwrite anything -- the second run creates a folder with `_2` appended, the third gets `_3`, and so on.

## Project Structure

```
main.py                  # CLI entry point
manager/
  agent.py               # Orchestration & delegation
  classifier.py          # Keyword-scoring request classifier
agents/
  base.py                # Abstract base class
  web_agent.py           # Flask/HTML/CSS generation
  script_agent.py        # Python scripts & automation
  api_agent.py           # REST API generation
  data_agent.py          # Data analysis & CSV processing
  cli_agent.py           # CLI tools (argparse)
templates/
  web/                   # Flask app templates
  script/                # Script templates
  api/                   # API templates
  data/                  # Data analysis templates
  cli/                   # CLI tool templates
utils/
  template_engine.py     # string.Template-based renderer
  folder_naming.py       # Slug generation & dedup
```
