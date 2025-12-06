"""Markdown formatter for code review reports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Finding, ReviewReport

from ..models import Severity


def format_report(report: ReviewReport) -> str:
    """Format a ReviewReport as markdown.

    Args:
        report: The review report to format

    Returns:
        Formatted markdown string
    """
    lines: list[str] = []

    # Header
    lines.append("# Code Review Report\n")

    # Summary
    lines.append("## Summary\n")
    lines.append(f"- **Files Reviewed**: {report.files_reviewed}")
    lines.append(
        f"- **Critical**: {report.critical_count} | "
        f"**High**: {report.high_count} | "
        f"**Medium**: {report.medium_count} | "
        f"**Low**: {report.low_count}"
    )
    lines.append(f"- **Total Findings**: {report.total_findings}\n")

    # Final verdict from reviewer agent
    if report.verdict:
        v = report.verdict
        lines.append(f"## Final Verdict: {v.decision.value}\n")
        lines.append(f"> {v.summary}\n")
        if v.reasoning:
            lines.append(f"{v.reasoning}\n")
        if v.key_concerns:
            lines.append("\n**Key Concerns:**")
            for concern in v.key_concerns:
                lines.append(f"- {concern}")
            lines.append("")
    else:
        # Fallback quick verdict
        if report.critical_count > 0:
            lines.append("> **Recommendation**: Request changes - critical issues found\n")
        elif report.high_count > 0:
            lines.append("> **Recommendation**: Request changes - high severity issues found\n")
        elif report.medium_count > 0:
            lines.append("> **Recommendation**: Consider addressing medium severity issues\n")
        elif report.low_count > 0:
            lines.append("> **Recommendation**: Minor improvements suggested\n")
        else:
            lines.append("> **Recommendation**: Approve - no issues found\n")

    lines.append("---\n")

    # Findings by severity
    if report.critical_count > 0:
        lines.append("## Critical Findings\n")
        _add_findings_section(lines, report.findings, Severity.CRITICAL)
        lines.append("---\n")

    if report.high_count > 0:
        lines.append("## High Severity Findings\n")
        _add_findings_section(lines, report.findings, Severity.HIGH)
        lines.append("---\n")

    if report.medium_count > 0:
        lines.append("## Medium Severity Findings\n")
        _add_findings_section(lines, report.findings, Severity.MEDIUM)
        lines.append("---\n")

    if report.low_count > 0:
        lines.append("## Low Severity Findings\n")
        _add_findings_section(lines, report.findings, Severity.LOW)

    # Agent breakdown (optional verbose section)
    if report.agent_results:
        lines.append("\n---\n")
        lines.append("## Agent Breakdown\n")
        for result in report.agent_results:
            agent_findings = len(result.findings)
            status = "error" if result.error else f"{agent_findings} findings"
            lines.append(f"- **{result.agent_name.title()}**: {status}")
            if result.error:
                lines.append(f"  - Error: {result.error}")

    return "\n".join(lines)


def _add_findings_section(
    lines: list[str],
    findings: list[Finding],
    severity: Severity,
) -> None:
    """Add findings of a specific severity to the output.

    Args:
        lines: List to append lines to
        findings: All findings
        severity: Severity level to filter
    """
    filtered = [f for f in findings if f.severity == severity]

    for i, finding in enumerate(filtered, 1):
        # Category badge
        category_badge = f"[{finding.category.value.upper()}]"

        # Title with location
        location = finding.file_path
        if finding.line_number:
            location = f"{location}:{finding.line_number}"

        lines.append(f"### {i}. {category_badge} {finding.title}")
        lines.append(f"**File**: `{location}`\n")

        # Description
        lines.append(finding.description)
        lines.append("")

        # Code snippet if available
        if finding.code_snippet:
            lines.append("**Code**:")
            lines.append("```")
            lines.append(finding.code_snippet.strip())
            lines.append("```")
            lines.append("")

        # Suggested fix if available
        if finding.suggested_fix:
            lines.append("**Suggested Fix**:")
            # Check if it looks like code
            if "\n" in finding.suggested_fix or "def " in finding.suggested_fix:
                lines.append("```")
                lines.append(finding.suggested_fix.strip())
                lines.append("```")
            else:
                lines.append(f"> {finding.suggested_fix}")
            lines.append("")

        lines.append("")


def format_finding_compact(finding: Finding) -> str:
    """Format a single finding in compact format.

    Args:
        finding: The finding to format

    Returns:
        Single-line compact representation
    """
    location = finding.file_path
    if finding.line_number:
        location = f"{location}:{finding.line_number}"

    severity_emoji = {
        Severity.CRITICAL: "!!",
        Severity.HIGH: "!",
        Severity.MEDIUM: "*",
        Severity.LOW: "-",
    }

    emoji = severity_emoji.get(finding.severity, "?")
    return f"{emoji} [{finding.category.value}] {finding.title} ({location})"
