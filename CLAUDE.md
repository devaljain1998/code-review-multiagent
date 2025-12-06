# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent code review system that uses specialized AI agents (Security, Bug, Style) running in parallel to analyze git commits and GitHub PRs. Built on AWS Bedrock with Claude models.

## Commands

```bash
# Install in development mode
pip install -e .

# Run linter
ruff check .

# Run tests
pytest tests/

# CLI usage
code-review HEAD                                    # Review last commit
code-review abc123f                                 # Review specific commit
code-review https://github.com/owner/repo/pull/123  # Review GitHub PR (requires gh CLI)
code-review owner/repo#123                          # Shorthand PR format
code-review feature-branch --base main              # Compare branches
code-review HEAD --verbose                          # Show agent details
code-review HEAD --json-output                      # JSON output for CI/CD
```

## Architecture

### Provider Abstraction (`providers/`)
- `base.py`: `LLMProvider` Protocol defining `invoke()` and `stream()` methods
- `bedrock.py`: AWS Bedrock implementation using inference profiles
- `agent_sdk.py`: Placeholder for future Claude Agent SDK

Model tiers:
- `"fast"`: Claude Haiku 4.5 - used by sub-agents for cost efficiency
- `"smart"`: Claude Sonnet 4.5 - used by orchestrator for synthesis

### Agent System (`agents/`)
- `base.py`: `BaseAgent` abstract class with provider injection
- Each agent (security, bugs, style) extends `BaseAgent` and provides specialized prompts
- Agents are provider-agnostic - they work with any `LLMProvider` implementation

### Orchestrator Flow
1. CLI parses target (commit/branch/GitHub PR URL)
2. Git diff is fetched (via git or `gh` CLI for GitHub PRs)
3. Files are parsed and filtered by language (Python/Go)
4. Three agents run **in parallel** via `asyncio.gather()`
5. Results are aggregated into `ReviewReport`
6. Markdown report is generated with severity-ranked findings

### Key Data Models (`models.py`)
- `GitHubPR`: Parsed GitHub PR info (owner, repo, number)
- `FileChange`: Diff + metadata for a single file
- `Finding`: Single issue with severity, location, suggested fix
- `ReviewResult`: One agent's findings
- `ReviewReport`: Aggregated report with counts and all findings

## Environment

```bash
export AWS_REGION=us-west-2
export AWS_PROFILE=your-profile  # If using AWS SSO
```

## Exit Codes

- `0`: No critical/high issues
- `1`: High severity issues found
- `2`: Critical issues found
- `3`: Execution error

## Adding New Functionality

### New Provider
1. Create `providers/new_provider.py` implementing `LLMProvider` protocol
2. Add to factory in `providers/base.py`
3. Add CLI choice in `cli.py`

### New Agent
1. Create `agents/new_agent.py` extending `BaseAgent`
2. Add prompt in `prompts/new_agent.py`
3. Register in orchestrator's `__init__` and `review()` method
