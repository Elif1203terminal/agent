#!/usr/bin/env python3
"""AgentsOne - Multi-Agent Code Generation System.

Usage:
    python main.py "build me a todo web app"
    python main.py "create a REST API for user management"
    python main.py --list-agents
    python main.py --dry-run "build a CLI tool"
"""

import argparse
import sys

from manager.agent import ManagerAgent


def main():
    parser = argparse.ArgumentParser(
        prog="agentsone",
        description="Multi-agent code generation system",
    )
    parser.add_argument("request", nargs="?", help="Natural language request")
    parser.add_argument("--list-agents", action="store_true", help="List available agents")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without writing files")

    args = parser.parse_args()
    manager = ManagerAgent()

    if args.list_agents:
        print("Available agents:")
        for name, desc in manager.list_agents():
            print(f"  {name:10s} - {desc}")
        return

    if not args.request:
        parser.print_help()
        sys.exit(1)

    result = manager.handle(args.request, dry_run=args.dry_run)

    if args.dry_run:
        print(f"Category: {result['category']} (agent: {result['agent']})")
        print(f"Scores: {result['scores']}")
        print("\nPlan:")
        for step in result["plan"]:
            print(f"  {step}")
        return

    print(f"Category: {result['category']} (agent: {result['agent']})")
    print(f"Output:   {result['output_dir']}")
    print(f"\nGenerated {len(result['files'])} file(s):")
    for f in result["files"]:
        print(f"  {f}")


if __name__ == "__main__":
    main()
