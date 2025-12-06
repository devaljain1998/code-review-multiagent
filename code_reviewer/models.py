"""Pydantic models for the code review system."""

from enum import Enum
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingCategory(str, Enum):
    """Category of finding."""

    SECURITY = "security"
    BUG = "bug"
    STYLE = "style"


class ReviewDecision(str, Enum):
    """Final review decision from the reviewer agent."""

    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


class FinalVerdict(BaseModel):
    """Final verdict from the reviewer agent."""

    decision: ReviewDecision = Field(..., description="The review decision")
    summary: str = Field(..., description="One-line summary of the decision")
    reasoning: str = Field(..., description="2-3 sentences explaining the decision")
    key_concerns: list[str] = Field(
        default_factory=list, description="Top concerns if any (empty if APPROVE)"
    )


class Message(BaseModel):
    """A message in the conversation."""

    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ModelResponse(BaseModel):
    """Response from an LLM invocation."""

    content: str = Field(..., description="Response text content")
    model_id: str | None = Field(default=None, description="Model that generated response")
    usage: dict | None = Field(default=None, description="Token usage info")


class FileChange(BaseModel):
    """A changed file in a diff."""

    path: str = Field(..., description="File path")
    language: str = Field(..., description="Programming language (py, go, etc.)")
    diff: str = Field(..., description="The diff hunk for this file")
    content: str | None = Field(default=None, description="Full file content if available")


class Finding(BaseModel):
    """A single finding from a review agent."""

    category: FindingCategory = Field(..., description="Type of finding")
    severity: Severity = Field(..., description="Severity level")
    title: str = Field(..., description="Short title of the finding")
    description: str = Field(..., description="Detailed description")
    file_path: str = Field(..., description="File where issue was found")
    line_number: int | None = Field(default=None, description="Line number if applicable")
    code_snippet: str | None = Field(default=None, description="Relevant code snippet")
    suggested_fix: str | None = Field(default=None, description="Suggested fix if available")


class ReviewResult(BaseModel):
    """Result from a single review agent."""

    agent_name: str = Field(..., description="Name of the agent that produced this result")
    findings: list[Finding] = Field(default_factory=list, description="List of findings")
    files_reviewed: list[str] = Field(default_factory=list, description="Files that were reviewed")
    error: str | None = Field(default=None, description="Error message if review failed")


class ReviewReport(BaseModel):
    """Final aggregated review report."""

    files_reviewed: int = Field(..., description="Total files reviewed")
    total_findings: int = Field(..., description="Total number of findings")
    critical_count: int = Field(default=0, description="Critical severity count")
    high_count: int = Field(default=0, description="High severity count")
    medium_count: int = Field(default=0, description="Medium severity count")
    low_count: int = Field(default=0, description="Low severity count")
    findings: list[Finding] = Field(default_factory=list, description="All findings sorted by severity")
    agent_results: list[ReviewResult] = Field(
        default_factory=list, description="Individual agent results"
    )
    verdict: FinalVerdict | None = Field(
        default=None, description="Final verdict from reviewer agent"
    )

    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        from .output.markdown import format_report

        return format_report(self)

    @classmethod
    def from_agent_results(
        cls,
        results: list[ReviewResult],
        verdict: "FinalVerdict | None" = None,
    ) -> "ReviewReport":
        """Create a report from multiple agent results.

        Args:
            results: List of agent review results
            verdict: Optional final verdict from reviewer agent
        """
        all_findings: list[Finding] = []
        files_reviewed: set[str] = set()

        for result in results:
            all_findings.extend(result.findings)
            files_reviewed.update(result.files_reviewed)

        # Sort findings by severity
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        all_findings.sort(key=lambda f: severity_order[f.severity])

        # Count by severity
        counts = {s: 0 for s in Severity}
        for finding in all_findings:
            counts[finding.severity] += 1

        return cls(
            files_reviewed=len(files_reviewed),
            total_findings=len(all_findings),
            critical_count=counts[Severity.CRITICAL],
            high_count=counts[Severity.HIGH],
            medium_count=counts[Severity.MEDIUM],
            low_count=counts[Severity.LOW],
            findings=all_findings,
            agent_results=results,
            verdict=verdict,
        )
