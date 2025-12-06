"""Reviewer agent for final PR decision."""

import json
import re

from ..models import (
    FinalVerdict,
    Message,
    ReviewDecision,
    ReviewResult,
)
from ..prompts.reviewer import REVIEWER_SYSTEM_PROMPT
from ..providers.base import LLMProvider


class ReviewerAgent:
    """Agent that synthesizes findings and makes final PR decision.

    Unlike other agents that analyze code directly, the ReviewerAgent
    takes the findings from all other agents and makes a final verdict.
    """

    AGENT_NAME = "reviewer"

    def __init__(self, provider: LLMProvider, model_tier: str = "smart"):
        """Initialize the reviewer agent.

        Args:
            provider: LLM provider instance
            model_tier: Uses "smart" tier by default for better synthesis
        """
        self.provider = provider
        self.model_tier = model_tier

    def get_system_prompt(self) -> str:
        """Return the reviewer system prompt."""
        return REVIEWER_SYSTEM_PROMPT

    async def synthesize(
        self,
        agent_results: list[ReviewResult],
        files_context: str,
    ) -> FinalVerdict:
        """Synthesize agent findings into a final verdict.

        Args:
            agent_results: Results from Security, Bug, Style agents
            files_context: Summary of files reviewed

        Returns:
            FinalVerdict with decision and reasoning
        """
        # Format findings for the reviewer
        findings_summary = self._format_findings(agent_results)

        # Count findings by severity
        severity_counts = self._count_severities(agent_results)

        prompt = f"""## Files Reviewed
{files_context}

## Finding Summary
- Critical: {severity_counts['critical']}
- High: {severity_counts['high']}
- Medium: {severity_counts['medium']}
- Low: {severity_counts['low']}

## Agent Findings

{findings_summary}

Based on these findings, provide your final review decision as a JSON object."""

        messages = [Message(role="user", content=prompt)]

        response = await self.provider.invoke(
            messages=messages,
            system_prompt=self.get_system_prompt(),
            model_tier=self.model_tier,
        )

        return self._parse_verdict(response.content, severity_counts)

    def _format_findings(self, results: list[ReviewResult]) -> str:
        """Format agent results for the reviewer.

        Args:
            results: List of ReviewResult from each agent

        Returns:
            Formatted string of all findings
        """
        sections = []

        for result in results:
            if result.error:
                sections.append(f"### {result.agent_name.title()} Agent\nError: {result.error}")
                continue

            if not result.findings:
                sections.append(f"### {result.agent_name.title()} Agent\nNo issues found.")
                continue

            findings_text = []
            for f in result.findings:
                line_info = f":{f.line_number}" if f.line_number else ""
                findings_text.append(
                    f"- [{f.severity.value.upper()}] {f.title} ({f.file_path}{line_info})"
                )

            section = f"### {result.agent_name.title()} Agent\n" + "\n".join(findings_text)
            sections.append(section)

        return "\n\n".join(sections) if sections else "No findings from any agent."

    def _count_severities(self, results: list[ReviewResult]) -> dict[str, int]:
        """Count findings by severity across all results.

        Args:
            results: List of ReviewResult from each agent

        Returns:
            Dict mapping severity name to count
        """
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for result in results:
            for finding in result.findings:
                severity = finding.severity.value.lower()
                if severity in counts:
                    counts[severity] += 1

        return counts

    def _parse_verdict(
        self,
        content: str,
        severity_counts: dict[str, int],
    ) -> FinalVerdict:
        """Parse LLM response into FinalVerdict.

        Args:
            content: Raw response from LLM
            severity_counts: Counts of each severity level

        Returns:
            FinalVerdict object
        """
        try:
            # Try to extract JSON from response
            # Handle both raw JSON and JSON in code blocks
            json_match = re.search(r'\{[^{}]*"decision"[^{}]*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Try parsing the whole content as JSON
                data = json.loads(content)

            return FinalVerdict(
                decision=ReviewDecision(data["decision"]),
                summary=data.get("summary", ""),
                reasoning=data.get("reasoning", ""),
                key_concerns=data.get("key_concerns", []),
            )

        except (json.JSONDecodeError, KeyError, ValueError):
            # Fallback: determine decision based on severity counts
            return self._fallback_verdict(content, severity_counts)

    def _fallback_verdict(
        self,
        content: str,
        severity_counts: dict[str, int],
    ) -> FinalVerdict:
        """Generate a verdict when JSON parsing fails.

        Args:
            content: Raw response content (used for reasoning)
            severity_counts: Counts of each severity level

        Returns:
            FinalVerdict based on severity counts
        """
        content_lower = content.lower()

        # Determine decision based on findings
        if severity_counts["critical"] > 0:
            decision = ReviewDecision.REQUEST_CHANGES
            summary = f"Critical issues found ({severity_counts['critical']} critical)"
        elif severity_counts["high"] >= 2:
            decision = ReviewDecision.REQUEST_CHANGES
            summary = f"Multiple high severity issues ({severity_counts['high']} high)"
        elif severity_counts["high"] == 1:
            decision = ReviewDecision.COMMENT
            summary = "One high severity issue to consider"
        elif severity_counts["medium"] > 0:
            decision = ReviewDecision.COMMENT
            summary = f"Medium severity issues found ({severity_counts['medium']} medium)"
        else:
            decision = ReviewDecision.APPROVE
            summary = "No significant issues found"

        # Override with explicit keywords if present
        if "request_changes" in content_lower or "must be fixed" in content_lower:
            decision = ReviewDecision.REQUEST_CHANGES
        elif "approve" in content_lower and severity_counts["critical"] == 0:
            decision = ReviewDecision.APPROVE

        return FinalVerdict(
            decision=decision,
            summary=summary,
            reasoning=content[:500] if content else "Based on automated severity analysis",
            key_concerns=[],
        )
