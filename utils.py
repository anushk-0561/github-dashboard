"""
utils.py
========
Pure helper functions: language aggregation (byte-accurate), streak
calculation, heatmap matrix generation, and report builders.
Everything here is testable without network calls.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Any


def aggregate_languages(repos: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """
    Aggregate language statistics using byte counts from the /languages endpoint.
    Returns a list of (language_name, percentage) sorted by percentage desc.
    """
    if not repos:
        return []

    byte_counter: Counter[str] = Counter()
    total_bytes = 0

    for repo in repos:
        # Each repo should have a 'languages' dict from the API
        languages = repo.get("languages", {})
        if not languages:
            continue
        for lang, bytes_count in languages.items():
            byte_counter[lang] += bytes_count
            total_bytes += bytes_count

    if total_bytes == 0:
        return []

    # Convert to percentages and sort
    result = [(lang, (count / total_bytes) * 100) for lang, count in byte_counter.most_common(5)]
    # Round to 1 decimal place for cleaner display
    return [(lang, round(pct, 1)) for lang, pct in result]


def repo_highlights(repos: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute total stars/forks and find most starred/forked repos."""
    if not repos:
        return {"total_stars": 0, "total_forks": 0, "most_starred": None, "most_forked": None}

    total_stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    total_forks = sum(repo.get("forks_count", 0) for repo in repos)

    # Find most starred (if any)
    most_starred = max(repos, key=lambda r: r.get("stargazers_count", 0)) if repos else None
    most_forked = max(repos, key=lambda r: r.get("forks_count", 0)) if repos else None

    return {
        "total_stars": total_stars,
        "total_forks": total_forks,
        "most_starred": {
            "name": most_starred["name"],
            "stars": most_starred.get("stargazers_count", 0),
        } if most_starred else None,
        "most_forked": {
            "name": most_forked["name"],
            "forks": most_forked.get("forks_count", 0),
        } if most_forked else None,
    }


def compute_streaks(calendar: dict[str, Any]) -> dict[str, int]:
    """
    Calculate current streak, longest streak, and total contributions
    from the contribution calendar (last 52 weeks).
    """
    if not calendar or "weeks" not in calendar:
        return {"current": 0, "longest": 0, "total": 0}

    # Flatten all contribution days
    days = []
    for week in calendar.get("weeks", []):
        for day in week.get("contributionDays", []):
            days.append({
                "date": day["date"],
                "count": day["contributionCount"],
            })

    if not days:
        return {"current": 0, "longest": 0, "total": 0}

    # Total contributions
    total = sum(d["count"] for d in days)

    # Sort by date (oldest to newest)
    days_sorted = sorted(days, key=lambda d: d["date"])

    # Calculate streaks (consecutive days with contributionCount > 0)
    current_streak = 0
    longest_streak = 0
    streak = 0

    for day in days_sorted:
        if day["count"] > 0:
            streak += 1
            longest_streak = max(longest_streak, streak)
        else:
            streak = 0

    # Current streak (from most recent day going backwards)
    current_streak = 0
    for day in reversed(days_sorted):
        if day["count"] > 0:
            current_streak += 1
        else:
            break

    return {
        "current": current_streak,
        "longest": longest_streak,
        "total": total,
    }


def heatmap_level(count: int) -> int:
    """Convert contribution count to heatmap level (0-4) matching GitHub's shading."""
    if count == 0:
        return 0
    elif count <= 3:
        return 1
    elif count <= 6:
        return 2
    elif count <= 9:
        return 3
    else:
        return 4


def build_heatmap_matrix(calendar: dict[str, Any]) -> tuple[list[list[int]], list[str]]:
    """
    Build a 7-row (days) x N-column (weeks) matrix of contribution levels.
    Returns (matrix, month_labels).
    """
    if not calendar or "weeks" not in calendar:
        return [], []

    weeks = calendar.get("weeks", [])
    if not weeks:
        return [], []

    # Initialize 7 rows (Sunday to Saturday)
    matrix = [[0] * len(weeks) for _ in range(7)]

    # Month tracking for headers
    months = []

    for col, week in enumerate(weeks):
        days = week.get("contributionDays", [])
        for day in days:
            weekday = day.get("weekday", 0)  # 0 = Sunday
            count = day.get("contributionCount", 0)
            matrix[weekday][col] = heatmap_level(count)

        # Track month from first day of week (if available)
        if days and len(days) > 0:
            date_str = days[0]["date"]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            months.append(date_obj.strftime("%b"))

    return matrix, months


def build_report(
    user: dict[str, Any],
    repos: list[dict[str, Any]],
    languages: list[tuple[str, float]],
    streaks: dict[str, int] | None,
    highlights: dict[str, Any],
) -> dict[str, Any]:
    """Build a serializable report dictionary for JSON/Markdown export."""
    return {
        "username": user.get("login", "unknown"),
        "name": user.get("name"),
        "bio": user.get("bio"),
        "location": user.get("location"),
        "joined_at": user.get("created_at"),
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "top_languages": [{"language": lang, "percentage": pct} for lang, pct in languages[:5]],
        "streaks": streaks or {"current": 0, "longest": 0, "total": 0},
        "highlights": highlights,
    }


def export_json(report: dict[str, Any], filepath: str) -> None:
    """Export report as JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def export_markdown(report: dict[str, Any], filepath: str) -> None:
    """Export report as Markdown file."""
    lines = [
        f"# GitHub Stats: {report['username']}",
        "",
        f"**Name:** {report['name'] or 'N/A'}",
        f"**Bio:** {report['bio'] or 'N/A'}",
        f"**Location:** {report['location'] or 'N/A'}",
        f"**Joined:** {report['joined_at'].split('T')[0] if report['joined_at'] else 'N/A'}",
        "",
        "## Summary",
        f"- **Public Repos:** {report['public_repos']}",
        f"- **Followers:** {report['followers']}",
        f"- **Following:** {report['following']}",
        f"- **Total Stars:** {report['highlights']['total_stars']}",
        f"- **Total Forks:** {report['highlights']['total_forks']}",
        "",
        "## Top Languages",
    ]

    for lang in report["top_languages"]:
        lines.append(f"- **{lang['language']}:** {lang['percentage']}%")

    lines.extend([
        "",
        "## Streaks",
        f"- **Current Streak:** {report['streaks']['current']} days",
        f"- **Longest Streak:** {report['streaks']['longest']} days",
        f"- **Total Contributions (1 year):** {report['streaks']['total']}",
        "",
        "---",
        "*Generated by GitHub Activity Dashboard*",
    ])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        