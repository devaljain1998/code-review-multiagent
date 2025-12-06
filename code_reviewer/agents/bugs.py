"""Bug detection review agent."""

from ..models import FindingCategory
from ..prompts import BUGS_SYSTEM_PROMPT
from .base import BaseAgent


class BugAgent(BaseAgent):
    """Agent specialized in bug and logic error detection.

    Focuses on:
    - Logic errors and off-by-one bugs
    - Null/None reference issues
    - Exception handling problems
    - Resource leaks
    - Concurrency issues
    - Language-specific bugs (Python/Go)
    """

    AGENT_NAME = "bugs"
    FINDING_CATEGORY = FindingCategory.BUG

    def get_system_prompt(self) -> str:
        """Return the bug-detection system prompt."""
        return BUGS_SYSTEM_PROMPT
