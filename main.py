"""
main.py
=======
Entry point for the GitHub Activity Dashboard CLI.

Usage:
    python main.py <username>
    python main.py <username> --export json
    python main.py <username> --export md --output report.md
    python main.py --compare <user_a> <user_b>
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from rich.console import Console

from github_api import GitHubAPIError, GitHubClient
from display import render_compare, render_dashboard
from utils import (
    aggregate_languages,
    build_heatmap_matrix,
    build_report,
    compute_streaks,
    export_json,
    export_markdown,
    repo_highlights,
)

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="github-dashboard",
        description="Beautiful CLI dashboard for any public GitHub user.",
    )
    parser.add_argument("username", nargs="?", help="GitHub username to inspect")
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("USER_A", "USER_B"),
        help="Compare two GitHub users side-by-side",
    )
    parser.add_argument(
        "--export",
        choices=["json", "md"],
        help="Export the full report as JSON or Markdown",
    )
    parser.add_argument(
        "--output",
        help="Output file path (defaults to <username>_report.<ext>)",
    )
    return parser.parse_args()


def gather(client: GitHubClient, username: str, *, status) -> dict:
    """Fetch + compute everything we need for one user, with live status text."""
    status.update(f"[bold cyan]Fetching profile for [white]@{username}[/white]…")
    user = client.get_user(username)

    status.update(f"[bold cyan]Fetching repos for [white]@{username}[/white]…")
    repos = client.get_all_repos(username)

    languages = aggregate_languages(repos)
    highlights = repo_highlights(repos)

    streaks: dict | None = None
    calendar: dict | None = None
    try:
        status.update(f"[bold cyan]Fetching contribution graph for [white]@{username}[/white]…")
        calendar = client.get_contributions(username)
        streaks = compute_streaks(calendar)
    except GitHubAPIError as exc:
        # GraphQL needs a token; degrade gracefully if missing/invalid.
        console.print(f"[yellow]⚠ Streaks unavailable: {exc}[/yellow]")
        streaks = {"current": 0, "longest": 0, "total": 0}

    heatmap = build_heatmap_matrix(calendar) if calendar else None
    report = build_report(user, repos, languages, streaks, highlights)
    return {
        "user": user,
        "repos": repos,
        "languages": languages,
        "streaks": streaks,
        "highlights": highlights,
        "heatmap": heatmap,
        "report": report,
    }


def run_single(client: GitHubClient, username: str, export: str | None, output: str | None) -> None:
    with console.status("[bold cyan]Starting…", spinner="dots") as status:
        data = gather(client, username, status=status)

    render_dashboard(
        console,
        data["user"],
        data["languages"],
        data["streaks"],
        data["highlights"],
        data["heatmap"],
    )

    if export:
        ext = "json" if export == "json" else "md"
        path = output or f"{username}_report.{ext}"
        if export == "json":
            export_json(data["report"], path)
        else:
            export_markdown(data["report"], path)
        console.print(f"\n[bold green]✓ Report exported to {path}[/bold green]")


def run_compare(client: GitHubClient, user_a: str, user_b: str) -> None:
    with console.status("[bold cyan]Fetching users…", spinner="dots") as status:
        a = gather(client, user_a, status=status)
        b = gather(client, user_b, status=status)
    render_compare(console, a["report"], b["report"])


def main() -> int:
    load_dotenv()
    args = parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token or token.startswith("ghp_your"):
        console.print(
            "[yellow]ℹ No GITHUB_TOKEN set — using unauthenticated mode "
            "(60 requests/hour, no streaks/heatmap).[/yellow]"
        )

    client = GitHubClient(token=token)

    try:
        if args.compare:
            run_compare(client, args.compare[0], args.compare[1])
        elif args.username:
            run_single(client, args.username, args.export, args.output)
        else:
            console.print("[red]Error:[/red] provide a username or use --compare USER_A USER_B")
            return 2
    except GitHubAPIError as exc:
        console.print(f"[bold red]GitHub API error:[/bold red] {exc}")
        return 1
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
    