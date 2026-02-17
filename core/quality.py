"""Quality gate evaluation."""

from core.state import Iteration


def quality_gates_pass(iteration: Iteration) -> bool:
    """All three must pass: no errors from any source, lint passes, no security errors."""
    errors = [i for i in iteration.issues if i.severity == "error"]
    return len(errors) == 0 and iteration.lint_passed and iteration.security_passed
