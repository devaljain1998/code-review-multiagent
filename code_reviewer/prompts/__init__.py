"""Prompt templates for review agents."""

from .security import SECURITY_SYSTEM_PROMPT
from .bugs import BUGS_SYSTEM_PROMPT
from .style import STYLE_SYSTEM_PROMPT
from .orchestrator import SYNTHESIS_SYSTEM_PROMPT
from .reviewer import REVIEWER_SYSTEM_PROMPT

__all__ = [
    "SECURITY_SYSTEM_PROMPT",
    "BUGS_SYSTEM_PROMPT",
    "STYLE_SYSTEM_PROMPT",
    "SYNTHESIS_SYSTEM_PROMPT",
    "REVIEWER_SYSTEM_PROMPT",
]
