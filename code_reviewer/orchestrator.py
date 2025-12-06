"""Main orchestrator for multi-agent code review."""

import asyncio
import json

from .agents import BugAgent, ReviewerAgent, SecurityAgent, StyleAgent
from .git_utils import (
    enrich_files_with_content,
    filter_by_language,
    get_commit_diff,
    get_pr_diff,
    parse_diff,
)
from .models import Message, ReviewReport, ReviewResult
from .prompts.orchestrator import SYNTHESIS_SYSTEM_PROMPT
from .providers.base import LLMProvider, get_provider


class Orchestrator:
    """Main orchestrator for multi-agent code review.

    Coordinates multiple specialized agents (security, bugs, style) to
    review code changes in parallel, then synthesizes their findings
    into a unified report.

    The orchestrator is provider-agnostic - it works with any LLM backend
    that implements the LLMProvider protocol.
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        provider_type: str = "bedrock",
    ):
        """Initialize the orchestrator.

        Args:
            provider: Optional pre-configured provider instance
            provider_type: Provider type to create if provider not given
        """
        # Use injected provider or create from type
        self.provider = provider or get_provider(provider_type)

        # Initialize sub-agents with "fast" tier (Haiku for cost efficiency)
        self.security_agent = SecurityAgent(self.provider, model_tier="fast")
        self.bug_agent = BugAgent(self.provider, model_tier="fast")
        self.style_agent = StyleAgent(self.provider, model_tier="fast")

        # Initialize reviewer agent with "smart" tier (Sonnet for synthesis)
        self.reviewer_agent = ReviewerAgent(self.provider, model_tier="smart")

    async def review_commit(
        self,
        commit: str = "HEAD",
        repo_path: str | None = None,
        languages: list[str] | None = None,
    ) -> ReviewReport:
        """Review a specific commit.

        Args:
            commit: Commit hash or reference
            repo_path: Path to repository
            languages: Languages to review (default: python, go)

        Returns:
            ReviewReport with all findings
        """
        diff = get_commit_diff(commit, repo_path)
        return await self._review_diff(diff, commit, repo_path, languages)

    async def review_pr(
        self,
        base: str,
        head: str = "HEAD",
        repo_path: str | None = None,
        languages: list[str] | None = None,
    ) -> ReviewReport:
        """Review changes between two branches (PR review).

        Args:
            base: Base branch
            head: Head branch
            repo_path: Path to repository
            languages: Languages to review (default: python, go)

        Returns:
            ReviewReport with all findings
        """
        diff = get_pr_diff(base, head, repo_path)
        return await self._review_diff(diff, head, repo_path, languages)

    async def review_diff(
        self,
        diff: str,
        languages: list[str] | None = None,
    ) -> ReviewReport:
        """Review a raw diff string.

        Args:
            diff: Git diff string
            languages: Languages to review (default: python, go)

        Returns:
            ReviewReport with all findings
        """
        return await self._review_diff(diff, None, None, languages)

    async def _review_diff(
        self,
        diff: str,
        commit: str | None,
        repo_path: str | None,
        languages: list[str] | None,
    ) -> ReviewReport:
        """Internal method to review a diff.

        Args:
            diff: Git diff string
            commit: Commit reference for content retrieval
            repo_path: Repository path
            languages: Languages to include

        Returns:
            ReviewReport with all findings
        """
        # Parse diff into files
        files = parse_diff(diff)

        # Filter to supported languages
        files = filter_by_language(files, languages)

        if not files:
            return ReviewReport(
                files_reviewed=0,
                total_findings=0,
                findings=[],
                agent_results=[],
            )

        # Optionally enrich with full file content
        if commit and repo_path:
            files = enrich_files_with_content(files, commit, repo_path)

        # Convert FileChange to dict for agents
        files_data = [
            {
                "path": f.path,
                "language": f.language,
                "diff": f.diff,
                "content": f.content,
            }
            for f in files
        ]

        # Run all agents in parallel
        results = await asyncio.gather(
            self.security_agent.review(files_data),
            self.bug_agent.review(files_data),
            self.style_agent.review(files_data),
            return_exceptions=True,
        )

        # Handle any exceptions
        valid_results: list[ReviewResult] = []
        for result in results:
            if isinstance(result, Exception):
                # Create error result
                valid_results.append(
                    ReviewResult(
                        agent_name="unknown",
                        findings=[],
                        files_reviewed=[],
                        error=str(result),
                    )
                )
            else:
                valid_results.append(result)

        # Run reviewer agent to get final verdict
        files_context = "\n".join(
            f"- {f['path']} ({f['language']})" for f in files_data
        )
        try:
            verdict = await self.reviewer_agent.synthesize(valid_results, files_context)
        except Exception:
            # If reviewer fails, continue without verdict
            verdict = None

        # Create report from results with verdict
        report = ReviewReport.from_agent_results(valid_results, verdict=verdict)

        return report

    async def synthesize_report(self, results: list[ReviewResult]) -> ReviewReport:
        """Use the smart model to synthesize a final report.

        This method can be used to have the orchestrator (using Sonnet)
        refine and deduplicate findings from the sub-agents.

        Args:
            results: List of ReviewResult from agents

        Returns:
            Synthesized ReviewReport
        """
        # Format results for synthesis
        input_text = self._format_for_synthesis(results)

        # Use smart tier (Sonnet) for synthesis
        response = await self.provider.invoke(
            messages=[Message(role="user", content=input_text)],
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            model_tier="smart",
        )

        # Parse synthesized response
        return self._parse_synthesis_response(response.content, results)

    def _format_for_synthesis(self, results: list[ReviewResult]) -> str:
        """Format agent results for synthesis prompt.

        Args:
            results: List of ReviewResult

        Returns:
            Formatted string for synthesis
        """
        parts = ["Please synthesize the following code review findings:\n"]

        for result in results:
            parts.append(f"\n## {result.agent_name.upper()} Agent Findings\n")

            if result.error:
                parts.append(f"Error: {result.error}\n")
                continue

            if not result.findings:
                parts.append("No issues found.\n")
                continue

            for finding in result.findings:
                parts.append(f"\n### [{finding.severity.value.upper()}] {finding.title}\n")
                parts.append(f"File: {finding.file_path}")
                if finding.line_number:
                    parts.append(f":{finding.line_number}")
                parts.append(f"\n{finding.description}\n")

                if finding.code_snippet:
                    parts.append(f"```\n{finding.code_snippet}\n```\n")

                if finding.suggested_fix:
                    parts.append(f"Suggested fix: {finding.suggested_fix}\n")

        return "".join(parts)

    def _parse_synthesis_response(
        self,
        response: str,
        original_results: list[ReviewResult],
    ) -> ReviewReport:
        """Parse the synthesis response into a ReviewReport.

        Args:
            response: Raw response from synthesis
            original_results: Original agent results (fallback)

        Returns:
            ReviewReport
        """
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1

            if start != -1 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)

                # Use synthesized data if available, otherwise fall back
                # For now, just return the original aggregated report
                # Future: parse the synthesized findings
                pass
        except json.JSONDecodeError:
            pass

        # Fall back to simple aggregation
        return ReviewReport.from_agent_results(original_results)
