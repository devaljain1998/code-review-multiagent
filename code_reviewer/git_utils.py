"""Git utilities for diff parsing and extraction."""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import FileChange


@dataclass
class GitHubPR:
    """Parsed GitHub PR information."""

    owner: str
    repo: str
    number: int
    url: str


# Language detection by file extension
LANGUAGE_MAP = {
    ".py": "python",
    ".go": "go",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

# Languages we care about for review
SUPPORTED_LANGUAGES = {"python", "go"}


def get_commit_diff(commit: str = "HEAD", repo_path: str | None = None) -> str:
    """Get the diff for a specific commit.

    Args:
        commit: Commit hash or reference (default: HEAD)
        repo_path: Path to the repository (default: current directory)

    Returns:
        The diff string for the commit
    """
    cmd = ["git", "show", "--format=", "--patch", commit]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=True,
    )

    return result.stdout


def get_pr_diff(base: str, head: str = "HEAD", repo_path: str | None = None) -> str:
    """Get the diff between two branches/commits (for PR review).

    Args:
        base: Base branch or commit
        head: Head branch or commit (default: HEAD)
        repo_path: Path to the repository (default: current directory)

    Returns:
        The diff string between base and head
    """
    cmd = ["git", "diff", f"{base}...{head}"]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=True,
    )

    return result.stdout


def get_staged_diff(repo_path: str | None = None) -> str:
    """Get the diff for staged changes.

    Args:
        repo_path: Path to the repository (default: current directory)

    Returns:
        The diff string for staged changes
    """
    cmd = ["git", "diff", "--cached"]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=True,
    )

    return result.stdout


def parse_diff(diff_text: str) -> list[FileChange]:
    """Parse a git diff into individual file changes.

    Args:
        diff_text: Raw git diff output

    Returns:
        List of FileChange objects
    """
    if not diff_text.strip():
        return []

    files: list[FileChange] = []

    # Split diff by file
    # Pattern matches "diff --git a/path b/path"
    file_pattern = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)
    matches = list(file_pattern.finditer(diff_text))

    for i, match in enumerate(matches):
        file_path = match.group(2)

        # Get the diff content for this file
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(diff_text)
        file_diff = diff_text[start:end]

        # Detect language
        ext = Path(file_path).suffix.lower()
        language = LANGUAGE_MAP.get(ext, "other")

        files.append(
            FileChange(
                path=file_path,
                language=language,
                diff=file_diff,
                content=None,  # Full content loaded on demand
            )
        )

    return files


def filter_by_language(
    files: list[FileChange],
    languages: list[str] | None = None,
) -> list[FileChange]:
    """Filter files to only include supported languages.

    Args:
        files: List of FileChange objects
        languages: Languages to include (default: python, go)

    Returns:
        Filtered list of FileChange objects
    """
    if languages is None:
        languages = list(SUPPORTED_LANGUAGES)

    return [f for f in files if f.language in languages]


def get_file_content(file_path: str, commit: str = "HEAD", repo_path: str | None = None) -> str:
    """Get the content of a file at a specific commit.

    Args:
        file_path: Path to the file
        commit: Commit reference (default: HEAD)
        repo_path: Path to the repository (default: current directory)

    Returns:
        File content string
    """
    cmd = ["git", "show", f"{commit}:{file_path}"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        # File might not exist at this commit (new file)
        return ""


def enrich_files_with_content(
    files: list[FileChange],
    commit: str = "HEAD",
    repo_path: str | None = None,
) -> list[FileChange]:
    """Add full file content to FileChange objects.

    Args:
        files: List of FileChange objects
        commit: Commit reference for content
        repo_path: Path to the repository

    Returns:
        List of FileChange objects with content populated
    """
    enriched = []

    for file in files:
        content = get_file_content(file.path, commit, repo_path)
        enriched.append(
            FileChange(
                path=file.path,
                language=file.language,
                diff=file.diff,
                content=content if content else None,
            )
        )

    return enriched


# =============================================================================
# GitHub CLI Integration
# =============================================================================


def is_gh_available() -> bool:
    """Check if GitHub CLI (gh) is installed.

    Returns:
        True if gh CLI is found in PATH
    """
    return shutil.which("gh") is not None


def is_gh_authenticated() -> bool:
    """Check if GitHub CLI is authenticated.

    Returns:
        True if gh CLI is installed and authenticated
    """
    if not is_gh_available():
        return False

    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def parse_github_pr_url(url: str) -> GitHubPR | None:
    """Parse a GitHub PR URL into components.

    Supports formats:
    - https://github.com/owner/repo/pull/123
    - http://github.com/owner/repo/pull/123
    - github.com/owner/repo/pull/123
    - owner/repo#123

    Args:
        url: The URL or shorthand to parse

    Returns:
        GitHubPR object if valid, None otherwise
    """
    patterns = [
        # Full URL: https://github.com/owner/repo/pull/123
        r"(?:https?://)?github\.com/([^/]+)/([^/]+)/pull/(\d+)",
        # Short format: owner/repo#123
        r"^([^/]+)/([^#]+)#(\d+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, url.strip())
        if match:
            return GitHubPR(
                owner=match.group(1),
                repo=match.group(2),
                number=int(match.group(3)),
                url=url,
            )

    return None


def get_github_pr_diff(pr: GitHubPR) -> str:
    """Fetch PR diff using GitHub CLI.

    Args:
        pr: Parsed GitHub PR info

    Returns:
        The diff string for the PR

    Raises:
        RuntimeError: If gh CLI is not available or not authenticated
        subprocess.CalledProcessError: If gh command fails
    """
    if not is_gh_available():
        raise RuntimeError(
            "GitHub CLI (gh) is not installed. "
            "Install it from https://cli.github.com/ or use local git commands instead."
        )

    if not is_gh_authenticated():
        raise RuntimeError(
            "GitHub CLI is not authenticated. Run 'gh auth login' first."
        )

    cmd = [
        "gh",
        "pr",
        "diff",
        str(pr.number),
        "--repo",
        f"{pr.owner}/{pr.repo}",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout


def get_github_pr_info(pr: GitHubPR) -> dict:
    """Get PR metadata using GitHub CLI.

    Args:
        pr: Parsed GitHub PR info

    Returns:
        Dict with keys: title, author, baseRefName, headRefName, state, url

    Raises:
        RuntimeError: If gh CLI is not available or not authenticated
        subprocess.CalledProcessError: If gh command fails
    """
    if not is_gh_available():
        raise RuntimeError(
            "GitHub CLI (gh) is not installed. "
            "Install it from https://cli.github.com/"
        )

    if not is_gh_authenticated():
        raise RuntimeError(
            "GitHub CLI is not authenticated. Run 'gh auth login' first."
        )

    cmd = [
        "gh",
        "pr",
        "view",
        str(pr.number),
        "--repo",
        f"{pr.owner}/{pr.repo}",
        "--json",
        "title,author,baseRefName,headRefName,state,url",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )

    return json.loads(result.stdout)
