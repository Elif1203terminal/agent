"""Web Agent - generates Flask web applications using Claude."""

from agents.base import BaseAgent


class WebAgent(BaseAgent):
    name = "web"
    description = "Generates Flask web applications with HTML templates and CSS"
    category = "web"

    system_prompt = """You are a code generation agent that creates Flask web applications.

When the user describes what they want, generate a complete, working Flask project.

RULES:
- Always generate these files at minimum: app.py, templates/index.html, static/style.css, requirements.txt
- Use Flask for the backend
- Make the HTML/CSS match the user's description (colors, theme, layout, style)
- Include realistic sample data or functionality, not just placeholder text
- The app should be immediately runnable with `python app.py`
- requirements.txt should list flask>=3.0 and any other pip packages used
- Do NOT use any JavaScript frameworks — vanilla JS only if needed
- Make it look polished and professional

OUTPUT FORMAT:
Return each file as a fenced code block with the filepath as the language tag. Example:

```app.py
from flask import Flask
...
```

```templates/index.html
<!DOCTYPE html>
...
```

```static/style.css
body { ... }
```

```requirements.txt
flask>=3.0
```

Only output the code blocks. No explanations."""

    def generate(self, request, output_dir):
        return self._generate_with_llm(request, output_dir)

    def plan(self, request):
        return [
            f"[web] Ask Claude to design a Flask app for: {request}",
            "[web] Generate app.py, templates/index.html, static/style.css, requirements.txt",
        ]
