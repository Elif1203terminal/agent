"""Manager Agent - orchestrates classification and delegation to specialist agents."""

import os
from manager.classifier import classify
from agents.web_agent import WebAgent
from agents.script_agent import ScriptAgent
from agents.api_agent import ApiAgent
from agents.data_agent import DataAgent
from agents.cli_agent import CliAgent
from utils.folder_naming import get_output_dir


class ManagerAgent:
    def __init__(self):
        self.agents = {
            "web": WebAgent(),
            "script": ScriptAgent(),
            "api": ApiAgent(),
            "data": DataAgent(),
            "cli": CliAgent(),
        }

    def list_agents(self):
        """Return a list of (name, description) tuples for all agents."""
        return [(a.name, a.description) for a in self.agents.values()]

    def handle(self, request, dry_run=False):
        """Classify the request, delegate to the right agent, return results."""
        category, scores = classify(request)
        agent = self.agents[category]

        if dry_run:
            steps = agent.plan(request)
            return {
                "category": category,
                "agent": agent.name,
                "scores": scores,
                "dry_run": True,
                "plan": steps,
            }

        output_dir = get_output_dir(category, request)
        os.makedirs(output_dir, exist_ok=True)

        files = agent.generate(request, output_dir)

        return {
            "category": category,
            "agent": agent.name,
            "scores": scores,
            "output_dir": output_dir,
            "files": files,
        }
