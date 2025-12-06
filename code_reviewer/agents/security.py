"""Security review agent."""

from ..models import FindingCategory
from ..prompts import SECURITY_SYSTEM_PROMPT
from .base import BaseAgent


class SecurityAgent(BaseAgent):
    """Agent specialized in security vulnerability detection.

    Focuses on:
    - OWASP Top 10 vulnerabilities
    - Injection flaws (SQL, command, XSS)
    - Authentication/authorization issues
    - Hardcoded secrets and credentials
    - Language-specific security issues (Python/Go)
    """

    AGENT_NAME = "security"
    FINDING_CATEGORY = FindingCategory.SECURITY

    def get_system_prompt(self) -> str:
        """Return the security-focused system prompt."""
        return SECURITY_SYSTEM_PROMPT
