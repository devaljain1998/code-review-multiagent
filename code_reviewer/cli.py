"""CLI entry point for the code reviewer."""

import asyncio
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .git_utils import (
    get_commit_diff,
    get_github_pr_diff,
    get_github_pr_info,
    get_pr_diff,
    parse_github_pr_url,
)
from .orchestrator import Orchestrator

console = Console()


@click.command()
@click.argument("target", default="HEAD")
@click.option(
    "--base",
    "-b",
    help="Base branch for PR review (e.g., main). If provided, reviews diff from base to target.",
)
@click.option(
    "--provider",
    "-p",
    default="bedrock",
    type=click.Choice(["bedrock", "agent-sdk"]),
    help="LLM provider to use for review.",
)
@click.option(
    "--languages",
    "-l",
    default="python,go",
    help="Comma-separated list of languages to review (default: python,go).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show verbose output including agent details.",
)
@click.option(
    "--json-output",
    "-j",
    is_flag=True,
    help="Output results as JSON instead of markdown.",
)
def review(
    target: str,
    base: str | None,
    provider: str,
    languages: str,
    verbose: bool,
    json_output: bool,
) -> None:
    """Review code changes with AI agents.

    TARGET can be:

    \b
    - A commit hash (e.g., abc123f)
    - A branch name (e.g., HEAD, main)
    - A GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
    - A GitHub PR shorthand (e.g., owner/repo#123)

    Examples:

    \b
        # Review the last commit
        code-review HEAD

        # Review a specific commit
        code-review abc123f

        # Review a GitHub PR by URL (requires gh CLI)
        code-review https://github.com/owner/repo/pull/123

        # Review using shorthand format
        code-review owner/repo#123

        # Review a PR (diff from main to feature branch)
        code-review feature-branch --base main

        # Use specific provider
        code-review HEAD --provider bedrock
    """
    try:
        # Parse languages
        lang_list = [lang.strip() for lang in languages.split(",")]

        # Check if target is a GitHub PR URL
        github_pr = parse_github_pr_url(target)

        # Create orchestrator
        orchestrator = Orchestrator(provider_type=provider)

        if github_pr:
            # GitHub PR URL detected - use gh CLI
            if not json_output:
                console.print(
                    f"[bold blue]Reviewing GitHub PR #{github_pr.number}...[/bold blue]"
                )
                console.print(
                    f"[dim]Repository: {github_pr.owner}/{github_pr.repo}[/dim]"
                )

            try:
                # Fetch PR info for verbose output
                if verbose and not json_output:
                    pr_info = get_github_pr_info(github_pr)
                    console.print(f"[dim]Title: {pr_info.get('title', 'N/A')}[/dim]")
                    console.print(
                        f"[dim]Base: {pr_info.get('baseRefName')} ← "
                        f"Head: {pr_info.get('headRefName')}[/dim]"
                    )

                # Fetch diff via gh CLI
                diff = get_github_pr_diff(github_pr)

                if not json_output:
                    console.print(
                        f"[dim]Provider: {provider} | Languages: {', '.join(lang_list)}[/dim]\n"
                    )

                # Review the diff
                report = asyncio.run(
                    orchestrator.review_diff(diff, languages=lang_list)
                )

            except RuntimeError as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                console.print(
                    "[yellow]Tip: Install GitHub CLI from https://cli.github.com/[/yellow]"
                )
                sys.exit(3)

        elif base:
            # Local PR review (branch comparison)
            if not json_output:
                console.print(
                    f"[bold blue]Reviewing changes from {base} to {target}...[/bold blue]"
                )
                console.print(
                    f"[dim]Provider: {provider} | Languages: {', '.join(lang_list)}[/dim]\n"
                )

            report = asyncio.run(
                orchestrator.review_pr(base, target, languages=lang_list)
            )

        else:
            # Commit review
            if not json_output:
                console.print(f"[bold blue]Reviewing commit {target}...[/bold blue]")
                console.print(
                    f"[dim]Provider: {provider} | Languages: {', '.join(lang_list)}[/dim]\n"
                )

            report = asyncio.run(
                orchestrator.review_commit(target, languages=lang_list)
            )

        # Output results
        if json_output:
            click.echo(report.model_dump_json(indent=2))
        else:
            _display_report(report, verbose)

        # Exit code based on findings
        if report.critical_count > 0:
            sys.exit(2)  # Critical issues
        elif report.high_count > 0:
            sys.exit(1)  # High severity issues
        else:
            sys.exit(0)  # Success

    except Exception as e:
        if verbose:
            console.print_exception()
        else:
            console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(3)


def _display_report(report, verbose: bool) -> None:
    """Display the report using rich formatting.

    Args:
        report: The ReviewReport to display
        verbose: Whether to show verbose output
    """
    from .models import ReviewDecision, Severity

    # Summary panel
    if report.total_findings == 0:
        summary_style = "green"
        summary_text = "No issues found!"
    elif report.critical_count > 0:
        summary_style = "red"
        summary_text = "Critical issues require attention"
    elif report.high_count > 0:
        summary_style = "yellow"
        summary_text = "High severity issues found"
    else:
        summary_style = "blue"
        summary_text = "Minor issues found"

    console.print(
        Panel(
            f"[bold]{summary_text}[/bold]\n\n"
            f"Files: {report.files_reviewed} | "
            f"Critical: {report.critical_count} | "
            f"High: {report.high_count} | "
            f"Medium: {report.medium_count} | "
            f"Low: {report.low_count}",
            title="Review Summary",
            border_style=summary_style,
        )
    )
    console.print()

    # Display final verdict if available
    if report.verdict:
        verdict = report.verdict
        if verdict.decision == ReviewDecision.APPROVE:
            verdict_style = "green"
            verdict_icon = "APPROVE"
        elif verdict.decision == ReviewDecision.REQUEST_CHANGES:
            verdict_style = "red"
            verdict_icon = "REQUEST CHANGES"
        else:
            verdict_style = "yellow"
            verdict_icon = "COMMENT"

        verdict_content = f"[bold]{verdict_icon}[/bold]\n\n{verdict.summary}"
        if verdict.reasoning:
            verdict_content += f"\n\n[dim]{verdict.reasoning}[/dim]"

        console.print(
            Panel(
                verdict_content,
                title="Final Verdict",
                border_style=verdict_style,
            )
        )

        if verdict.key_concerns:
            console.print("\n[bold]Key Concerns:[/bold]")
            for concern in verdict.key_concerns:
                console.print(f"  - {concern}")

        console.print()

    # Display findings
    if report.findings:
        md = Markdown(report.to_markdown())
        console.print(md)

    # Verbose agent info
    if verbose and report.agent_results:
        console.print("\n[bold]Agent Details:[/bold]")
        for result in report.agent_results:
            status = "[red]error[/red]" if result.error else f"{len(result.findings)} findings"
            console.print(f"  - {result.agent_name}: {status}")
            if result.error:
                console.print(f"    [dim]{result.error}[/dim]")


@click.command()
def version() -> None:
    """Show version information."""
    from . import __version__

    console.print(f"code-reviewer version {__version__}")


# Create CLI group
@click.group()
def cli() -> None:
    """Multi-agent code review tool powered by Claude."""
    pass


cli.add_command(review)
cli.add_command(version)


if __name__ == "__main__":
    review()
