"""Code style review agent."""

from ..models import FindingCategory
from ..prompts import STYLE_SYSTEM_PROMPT
from .base import BaseAgent


class StyleAgent(BaseAgent):
    """Agent specialized in code style and best practices.

    Focuses on:
    - Naming conventions (PEP8/Go style)
    - Code structure and organization
    - Documentation quality
    - Language idioms and best practices
    - Import organization
    """

    AGENT_NAME = "style"
    FINDING_CATEGORY = FindingCategory.STYLE

    def get_system_prompt(self) -> str:
        """Return the style-focused system prompt."""
        return STYLE_SYSTEM_PROMPT
