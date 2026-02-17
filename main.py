#!/usr/bin/env python3
"""AgentsOne - Multi-Agent Code Generation System.

Usage:
    python main.py "build me a todo web app"                      # legacy single-shot
    python main.py build --prompt "build me a todo web app"       # pipeline mode
    python main.py build --prompt "..." --max-iters 2 --verbose   # pipeline with options
    python main.py build --prompt "..." --dry-run                 # plan only
    python main.py build --prompt "..." --type web                # override classifier
    python main.py list-agents
"""

import argparse
import os
import sys

from manager.agent import ManagerAgent
from core.orchestrator import Orchestrator
from utils.folder_naming import get_output_dir


def _format_issues(issues):
    """Format issues for CLI display."""
    lines = []
    for issue in issues:
        loc = issue.file
        if issue.line:
            loc += f":{issue.line}"
        marker = "ERROR" if issue.severity == "error" else "WARN"
        lines.append(f"  [{marker}] {loc} — {issue.message}")
        if issue.suggestion:
            lines.append(f"           Fix: {issue.suggestion}")
    return "\n".join(lines)


def _ask_user_approval(state, iteration):
    """Human-in-the-loop: show issues, ask whether to iterate."""
    errors = [i for i in iteration.issues if i.severity == "error"]
    warnings = [i for i in iteration.issues if i.severity == "warning"]

    print(f"\n--- Iteration {iteration.number} complete ---")
    print(f"  Lint passed:     {'yes' if iteration.lint_passed else 'NO'}")
    print(f"  Tests passed:    {'yes' if iteration.tests_passed else 'NO'}")
    print(f"  Security passed: {'yes' if iteration.security_passed else 'NO'}")
    print(f"  Errors: {len(errors)}  Warnings: {len(warnings)}")

    if errors or warnings:
        print("\nIssues found:")
        print(_format_issues(iteration.issues))

    remaining = state.max_iterations - iteration.number
    if remaining <= 0:
        print("\nMax iterations reached. Writing files as-is.")
        return False

    try:
        answer = input(f"\nRe-generate with fixes? ({remaining} iteration(s) left) [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    return answer in ("y", "yes")


def cmd_build(args):
    """Run the full agentic pipeline."""
    orchestrator = Orchestrator()
    output_dir = get_output_dir(args.type or "script", args.prompt)

    if args.dry_run:
        state = orchestrator.create_state(
            args.prompt, category=args.type, max_iterations=args.max_iters,
        )
        state = orchestrator.plan(state)
        print(f"Category: {state.category}")
        print(f"Stack:    {state.stack}")
        print(f"\nSpec:\n  {state.spec}")
        print(f"\nFile manifest:")
        for f in state.file_manifest:
            print(f"  {f}")
        return

    callback = _ask_user_approval if not args.no_loop else None

    state = orchestrator.run_full(
        request=args.prompt,
        category=args.type,
        max_iterations=args.max_iters,
        output_dir=output_dir,
        on_iteration=callback,
    )

    print(f"\nCategory: {state.category}")
    print(f"Stack:    {state.stack}")
    print(f"Output:   {state.output_dir}")
    print(f"Status:   {state.status}")
    print(f"Iterations: {len(state.iterations)}")
    print(f"\nGenerated {len(state.current_files)} file(s):")
    for f in state.current_files:
        print(f"  {f.path}")

    if args.verbose and state.iterations:
        for iteration in state.iterations:
            print(f"\n--- Iteration {iteration.number} ---")
            if iteration.issues:
                print(_format_issues(iteration.issues))
            else:
                print("  No issues found.")


def cmd_legacy(args):
    """Legacy single-shot mode (backward compat)."""
    manager = ManagerAgent()

    if args.dry_run:
        result = manager.handle(args.request, dry_run=True)
        print(f"Category: {result['category']} (agent: {result['agent']})")
        print(f"Scores: {result['scores']}")
        print("\nPlan:")
        for step in result["plan"]:
            print(f"  {step}")
        return

    result = manager.handle(args.request, dry_run=False)
    print(f"Category: {result['category']} (agent: {result['agent']})")
    print(f"Output:   {result['output_dir']}")
    print(f"\nGenerated {len(result['files'])} file(s):")
    for f in result["files"]:
        print(f"  {f}")


def main():
    parser = argparse.ArgumentParser(
        prog="agentsone",
        description="Multi-agent code generation system",
    )
    subparsers = parser.add_subparsers(dest="command")

    # build subcommand — new pipeline
    build_parser = subparsers.add_parser("build", help="Run the agentic build pipeline")
    build_parser.add_argument("--prompt", required=True, help="Natural language request")
    build_parser.add_argument("--type", choices=["web", "api", "cli", "data", "script"],
                              help="Override classifier category")
    build_parser.add_argument("--max-iters", type=int, default=2,
                              help="Max pipeline iterations (default: 2)")
    build_parser.add_argument("--verbose", action="store_true",
                              help="Show each iteration's issues")
    build_parser.add_argument("--dry-run", action="store_true",
                              help="Run planner only, show spec + file manifest")
    build_parser.add_argument("--no-loop", action="store_true",
                              help="Single iteration, no human-in-the-loop prompting")

    # list-agents subcommand
    subparsers.add_parser("list-agents", help="List available agents")

    # Legacy: positional request (backward compat)
    parser.add_argument("request", nargs="?", help="(Legacy) Natural language request")
    parser.add_argument("--list-agents", action="store_true", help="List available agents")
    parser.add_argument("--dry-run", action="store_true", dest="legacy_dry_run",
                        help="(Legacy) Show plan without writing files")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "list-agents" or args.list_agents:
        manager = ManagerAgent()
        print("Available agents:")
        for name, desc in manager.list_agents():
            print(f"  {name:10s} - {desc}")
        print("\nPipeline agents: planner, generator, reviewer, tester, security, patch_composer")
    elif args.request:
        # Legacy single-shot mode
        args.dry_run = args.legacy_dry_run
        cmd_legacy(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
