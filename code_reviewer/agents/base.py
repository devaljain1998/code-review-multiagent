"""Base agent class for code review agents."""

import json
from abc import ABC, abstractmethod

from ..models import Finding, FindingCategory, Message, ReviewResult, Severity
from ..providers.base import LLMProvider


class BaseAgent(ABC):
    """Base class for all review agents.

    Uses the provider abstraction layer so agents are decoupled from
    the specific LLM backend being used (Bedrock, Agent SDK, etc.).
    """

    # Override in subclasses
    AGENT_NAME: str = "base"
    FINDING_CATEGORY: FindingCategory = FindingCategory.BUG

    def __init__(self, provider: LLMProvider, model_tier: str = "fast"):
        """Initialize the agent.

        Args:
            provider: LLM provider instance (provider-agnostic)
            model_tier: "fast" (Haiku) or "smart" (Sonnet)
        """
        self.provider = provider
        self.model_tier = model_tier

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the agent-specific system prompt.

        Returns:
            System prompt string for this agent's specialty
        """
        raise NotImplementedError

    async def review(self, files: list[dict], context: dict | None = None) -> ReviewResult:
        """Review the provided files for issues.

        Args:
            files: List of file dicts with 'path', 'diff', 'content', 'language'
            context: Optional additional context

        Returns:
            ReviewResult with findings
        """
        if not files:
            return ReviewResult(
                agent_name=self.AGENT_NAME,
                findings=[],
                files_reviewed=[],
            )

        # Build the review prompt
        user_message = self._build_review_message(files, context)

        try:
            # Invoke the LLM
            response = await self._invoke(user_message)

            # Parse findings from response
            findings = self._parse_findings(response)

            return ReviewResult(
                agent_name=self.AGENT_NAME,
                findings=findings,
                files_reviewed=[f["path"] for f in files],
            )
        except Exception as e:
            return ReviewResult(
                agent_name=self.AGENT_NAME,
                findings=[],
                files_reviewed=[f["path"] for f in files],
                error=str(e),
            )

    async def _invoke(self, user_message: str) -> str:
        """Invoke the provider with this agent's system prompt.

        Args:
            user_message: The user message to send

        Returns:
            Response content string
        """
        response = await self.provider.invoke(
            messages=[Message(role="user", content=user_message)],
            system_prompt=self.get_system_prompt(),
            model_tier=self.model_tier,
        )
        return response.content

    def _build_review_message(self, files: list[dict], context: dict | None = None) -> str:
        """Build the review message from files.

        Args:
            files: List of file dicts
            context: Optional additional context

        Returns:
            Formatted message string
        """
        parts = ["Please review the following code changes:\n"]

        for file in files:
            parts.append(f"\n## File: {file['path']} ({file.get('language', 'unknown')})\n")
            parts.append("```diff\n")
            parts.append(file.get("diff", ""))
            parts.append("\n```\n")

            if file.get("content"):
                parts.append("\nFull file content for context:\n```\n")
                parts.append(file["content"][:5000])  # Limit content size
                if len(file.get("content", "")) > 5000:
                    parts.append("\n... (truncated)")
                parts.append("\n```\n")

        if context:
            parts.append(f"\nAdditional context: {json.dumps(context)}\n")

        return "".join(parts)

    def _parse_findings(self, response: str) -> list[Finding]:
        """Parse findings from the LLM response.

        Args:
            response: Raw response from LLM

        Returns:
            List of Finding objects
        """
        # Try to extract JSON from the response
        try:
            # Look for JSON array in response
            start = response.find("[")
            end = response.rfind("]") + 1

            if start != -1 and end > start:
                json_str = response[start:end]
                findings_data = json.loads(json_str)

                findings = []
                for item in findings_data:
                    try:
                        finding = Finding(
                            category=self.FINDING_CATEGORY,
                            severity=Severity(item.get("severity", "medium").lower()),
                            title=item.get("title", "Untitled finding"),
                            description=item.get("description", ""),
                            file_path=item.get("file_path", "unknown"),
                            line_number=item.get("line_number"),
                            code_snippet=item.get("code_snippet"),
                            suggested_fix=item.get("suggested_fix"),
                        )
                        findings.append(finding)
                    except Exception:
                        # Skip malformed findings
                        continue

                return findings
        except json.JSONDecodeError:
            pass

        return []
