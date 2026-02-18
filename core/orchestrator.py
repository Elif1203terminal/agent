"""Main pipeline orchestrator — state machine with human-in-the-loop gating."""

import os
import tempfile

from core.state import PipelineState, Iteration
from core.quality import quality_gates_pass
from config.defaults import DEFAULTS
from config.stacks import CATEGORY_TO_STACK
from manager.classifier import classify
from agents.planner import PlannerAgent
from agents.generator import GeneratorAgent
from agents.reviewer import ReviewerAgent
from agents.tester import TesterAgent
from agents.security import SecurityAgent
from agents.patch_composer import PatchComposer
from agents.readme_writer import ReadmeWriter


class Orchestrator:
    """Runs the full pipeline: classify → plan → generate → review → test → security.

    Human-in-the-loop: after each iteration, the caller decides whether to
    continue patching. The orchestrator never loops automatically.
    """

    def __init__(self):
        self.planner = PlannerAgent()
        self.generator = GeneratorAgent()
        self.reviewer = ReviewerAgent()
        self.tester = TesterAgent()
        self.security = SecurityAgent()
        self.patch_composer = PatchComposer()
        self.readme_writer = ReadmeWriter()

    def create_state(self, request, category=None, max_iterations=None, output_dir=None):
        """Create initial pipeline state.

        max_iterations is only used by run_full() for non-interactive (no callback) mode.
        In human-in-the-loop mode (server/UI), there's no soft limit — the human decides.
        The hard_max_iterations safety cap always applies.
        """
        hard_max = DEFAULTS["hard_max_iterations"]

        state = PipelineState(
            request=request,
            max_iterations=max_iterations or hard_max,
            output_dir=output_dir or "",
        )

        # Step 1: Classify
        if category:
            state.category = category
        else:
            state.category, scores = classify(request)
            # If the user explicitly named a tech, lock the stack now
            if "_explicit_stack" in scores:
                state.stack = scores["_explicit_stack"]

        if not state.stack:
            state.stack = CATEGORY_TO_STACK.get(state.category, "script")
        return state

    def plan(self, state: PipelineState) -> PipelineState:
        """Run the planner to produce spec + file manifest."""
        state = self.planner.run(state)
        return state

    def run_iteration(self, state: PipelineState) -> PipelineState:
        """Run one iteration: generate → review → test → security.

        Returns state with a new Iteration appended. The caller inspects
        the iteration to decide whether to approve or request patches.
        Does NOT automatically loop — that's the caller's decision.
        """
        hard_max = DEFAULTS["hard_max_iterations"]

        # Hard safety guard only — the human decides when to stop
        if len(state.iterations) >= hard_max:
            state.status = "done"
            state.errors.append(f"Hard safety limit reached ({hard_max}). Cannot run more iterations.")
            return state

        iteration_num = len(state.iterations) + 1

        # Generate (or patch)
        state = self.generator.run(state)

        # Review (1 LLM call)
        state = self.reviewer.run(state)
        review_issues = getattr(state, "_review_issues", [])

        # Test in sandbox (0 LLM calls)
        work_dir = tempfile.mkdtemp(prefix="agentsone_test_")
        state = self.tester.run(state, work_dir)
        test_issues = getattr(state, "_test_issues", [])
        lint_passed = getattr(state, "_lint_passed", True)
        tests_passed = getattr(state, "_tests_passed", True)

        # Security scan (0 LLM calls)
        state = self.security.run(state)
        security_issues = getattr(state, "_security_issues", [])

        # Collect all issues
        all_issues = review_issues + test_issues + security_issues
        security_passed = not any(
            i.severity == "error" for i in security_issues
        )

        # Create iteration record
        iteration = Iteration(
            number=iteration_num,
            files=list(state.current_files),
            issues=all_issues,
            lint_passed=lint_passed,
            tests_passed=tests_passed,
            security_passed=security_passed,
        )
        state.iterations.append(iteration)

        # Check quality gates
        if quality_gates_pass(iteration):
            state.status = "done"
        else:
            state.status = "awaiting_approval"
            # Prepare patch instructions in case user approves
            self.patch_composer.run(state, all_issues)

        return state

    def generate_readme(self, state: PipelineState) -> PipelineState:
        """Generate a README.md for the project. Runs after pipeline, 1 LLM call."""
        # Skip if no files or README already exists
        if not state.current_files:
            return state
        if any(f.path == "README.md" for f in state.current_files):
            return state
        return self.readme_writer.run(state)

    def write_files(self, state: PipelineState):
        """Write final files to disk."""
        if not state.output_dir:
            return []

        os.makedirs(state.output_dir, exist_ok=True)
        written = []
        for f in state.current_files:
            full_path = os.path.join(state.output_dir, f.path)
            resolved = os.path.realpath(full_path)
            if not resolved.startswith(os.path.realpath(state.output_dir) + os.sep):
                raise ValueError(f"Path escapes output directory: {f.path}")
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            with open(resolved, "w") as fp:
                fp.write(f.content)
            written.append(f.path)
        return written

    def run_full(self, request, category=None, max_iterations=None, output_dir=None,
                 on_iteration=None):
        """Run the full pipeline with a callback for human-in-the-loop approval.

        Args:
            request: User's natural language request.
            category: Optional override for classifier.
            max_iterations: Only used for non-interactive mode (no callback).
                            With a callback, the human decides when to stop.
            output_dir: Where to write final files.
            on_iteration: Callback function(state, iteration) -> bool.
                          Called after each iteration with issues.
                          Return True to approve another iteration, False to stop.
                          If None, stops after first iteration (no auto-looping).

        Returns:
            PipelineState with final results.
        """
        hard_max = DEFAULTS["hard_max_iterations"]
        # Non-interactive: use max_iterations (default 2). Interactive: hard_max only.
        loop_limit = hard_max if on_iteration else min(max_iterations or 2, hard_max)

        state = self.create_state(request, category, output_dir=output_dir)
        state = self.plan(state)

        for i in range(loop_limit):
            state = self.run_iteration(state)

            if state.status == "done":
                break

            if state.status == "awaiting_approval":
                if on_iteration:
                    should_continue = on_iteration(state, state.iterations[-1])
                    if not should_continue:
                        state.status = "done"
                        break
                else:
                    # No callback = no auto-looping, stop here
                    state.status = "done"
                    break

        # Generate README before writing
        state = self.generate_readme(state)

        # Write files
        if state.output_dir:
            self.write_files(state)

        if state.status != "failed":
            state.status = "done"

        return state
