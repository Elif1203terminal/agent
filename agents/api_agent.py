"""API Agent - generates REST API applications."""

import re
from agents.base import BaseAgent
from utils.template_engine import render_template


class ApiAgent(BaseAgent):
    name = "api"
    description = "Generates REST APIs with FastAPI or Flask"
    category = "api"

    def _extract_resource(self, request):
        """Extract the resource name from the request."""
        lower = request.lower()
        # Try to find "for <resource>" pattern
        match = re.search(r"(?:for|of)\s+(\w+(?:\s+\w+)?)\s*(?:management|tracking|system)?", lower)
        if match:
            resource = match.group(1).strip()
            # Remove "management", "tracking" etc.
            for suffix in ("management", "tracking", "system", "service"):
                resource = resource.replace(suffix, "").strip()
            return resource or "items"
        return "items"

    def _singularize(self, word):
        """Very basic singularization."""
        if word.endswith("ies"):
            return word[:-3] + "y"
        if word.endswith("ses"):
            return word[:-2]
        if word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
        return word

    def _pluralize(self, word):
        """Very basic pluralization."""
        if word.endswith("y") and word[-2] not in "aeiou":
            return word[:-1] + "ies"
        if word.endswith(("s", "sh", "ch", "x", "z")):
            return word + "es"
        return word + "s"

    def generate(self, request, output_dir):
        resource_raw = self._extract_resource(request)
        singular = self._singularize(resource_raw)
        plural = self._pluralize(singular)
        model_name = singular.capitalize()
        files = []

        # Use FastAPI template
        content = render_template("api", "fastapi_crud.py.tpl", {
            "app_name": f"{model_name} API",
            "model_name": model_name,
            "model_fields_create": f'name: str\n    description: Optional[str] = None',
            "model_fields_response": f'name: str\n    description: Optional[str] = None',
            "resource": plural,
        })
        files.append(self.write_file(output_dir, "app.py", content))

        # models.py
        content = render_template("api", "models.py.tpl", {
            "app_name": f"{model_name} API",
            "model_name": model_name,
            "resource_singular": singular,
            "init_params": "self, name, description=None",
            "init_body": f"self.name = name\n        self.description = description",
            "to_dict_body": f'"name": self.name,\n            "description": self.description,',
            "repr_fields": f'name={{self.name!r}}',
        })
        files.append(self.write_file(output_dir, "models.py", content))

        # requirements.txt
        files.append(self.write_file(output_dir, "requirements.txt", "fastapi>=0.100\nuvicorn>=0.23\n"))

        return files

    def plan(self, request):
        resource_raw = self._extract_resource(request)
        singular = self._singularize(resource_raw)
        model_name = singular.capitalize()
        return [
            f"[api] Create FastAPI CRUD app for {model_name}",
            "[api] Generate app.py with list/get/create/update/delete endpoints",
            "[api] Generate models.py",
            "[api] Generate requirements.txt",
        ]
