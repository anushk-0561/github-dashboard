"""
display.py
==========
All "make it pretty" code lives here. We use `rich` for panels, tables,
progress bars, and the heatmap rendering. Keeping rendering separate from
data fetching makes the modules easy to test independently.
"""

from __future__ import annotations

from typing import Any

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# 5-step colour ramp tuned for readability on a dark terminal.
HEAT_COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def render_profile_panel(user: dict[str, Any]) -> Panel:
    """Top-of-dashboard panel with basic profile info."""
    name = user.get("name") or user.get("login", "?")
    bio = user.get("bio") or "[dim]No bio[/dim]"
    location = user.get("location") or "[dim]Unknown[/dim]"
    created = (user.get("created_at") or "").split("T")[0] or "?"

    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    grid.add_row(
        Text(f"@{user.get('login', '')}", style="bold cyan"),
        Text(f"Joined {created}", style="dim"),
    )
    grid.add_row(Text(name, style="bold white"), Text(""))
    grid.add_row(Text(str(bio), style="italic"), Text(f"📍 {location}", style="magenta"))
    grid.add_row("", "")
    grid.add_row(
        Text(f"Repos: {user.get('public_repos', 0)}", style="green"),
        Text(
            f"Followers: {user.get('followers', 0)}  Following: {user.get('following', 0)}",
            style="yellow",
        ),
    )
    return Panel(grid, title="[bold]GitHub Profile[/bold]", border_style="cyan")


def render_languages_panel(langs: list[tuple[str, float]]) -> Panel:
    """Bar chart of top languages built from Unicode block characters."""
    if not langs:
        body = Text("No language data available.", style="dim")
    else:
        bar_width = 28
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()
        table.add_column(justify="right", style="cyan")
        for lang, pct in langs:
            filled = int(round(bar_width * pct / 100))
            bar = "█" * filled + "░" * (bar_width - filled)
            table.add_row(lang, Text(bar, style="green"), f"{pct}%")
        body = table
    return Panel(body, title="[bold]Top Languages[/bold]", border_style="green")


def render_streak_panel(streaks: dict[str, int]) -> Panel:
    """Three-up tile of streak metrics."""
    table = Table.grid(expand=True, padding=(0, 2))
    table.add_column(justify="center")
    table.add_column(justify="center")
    table.add_column(justify="center")

    def big(value: int, label: str, colour: str) -> Group:
        return Group(
            Text(str(value), style=f"bold {colour}", justify="center"),
            Text(label, style="dim", justify="center"),
        )

    table.add_row(
        big(streaks["current"], "Current streak (days)", "bright_green"),
        big(streaks["longest"], "Longest streak (days)", "yellow"),
        big(streaks["total"], "Contributions (1y)", "magenta"),
    )
    return Panel(table, title="[bold]Contribution Streaks[/bold]", border_style="yellow")


def render_highlights_panel(h: dict[str, Any]) -> Panel:
    """Stars / forks / top repos."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("⭐ Total stars", str(h.get("total_stars", 0)))
    table.add_row("🍴 Total forks", str(h.get("total_forks", 0)))
    if h.get("most_starred"):
        ms = h["most_starred"]
        table.add_row("Most starred", f"{ms['name']}  ({ms['stars']} ★)")
    if h.get("most_forked"):
        mf = h["most_forked"]
        table.add_row("Most forked", f"{mf['name']}  ({mf['forks']} forks)")
    return Panel(table, title="[bold]Repo Highlights[/bold]", border_style="magenta")


def render_heatmap_panel(matrix: list[list[int]], months: list[str]) -> Panel:
    """Render a GitHub-style contribution heatmap as coloured blocks."""
    from utils import heatmap_level  # local import avoids circular at top-level

    if not matrix or not matrix[0]:
        return Panel(Text("No contribution data.", style="dim"),
                     title="[bold]Contribution Heatmap[/bold]")

    cols = len(matrix[0])

    # Build month header row aligned over columns
    header = Text("    ")  # spacer for weekday labels column
    last = ""
    for m in months:
        if m and m != last:
            # Each cell ~2 chars wide -> stretch the label
            header.append(f"{m:<4}", style="bold dim")
            last = m
        else:
            header.append("  ", style="dim")
    # Trim/pad header to roughly match grid width
    if len(header.plain) < (cols * 2 + 4):
        header.append(" " * ((cols * 2 + 4) - len(header.plain)))

    rows: list[Text] = [header]
    for r in range(7):
        line = Text()
        # Show only Mon/Wed/Fri labels for cleanliness
        label = WEEKDAY_LABELS[r] if r in (1, 3, 5) else "   "
        line.append(f"{label} ", style="dim")
        for c in range(cols):
            level = heatmap_level(matrix[r][c])
            line.append("■ ", style=HEAT_COLORS[level])
        rows.append(line)

    legend = Text("\nLess ", style="dim")
    for col in HEAT_COLORS:
        legend.append("■ ", style=col)
    legend.append("More", style="dim")
    rows.append(legend)

    return Panel(Group(*rows),
                 title="[bold]Contribution Heatmap (last 52 weeks)[/bold]",
                 border_style="bright_blue")


def render_dashboard(
    console: Console,
    user: dict[str, Any],
    languages: list[tuple[str, float]],
    streaks: dict[str, int] | None,
    highlights: dict[str, Any],
    heatmap: tuple[list[list[int]], list[str]] | None,
) -> None:
    """Render the full dashboard to the supplied console."""
    console.print(render_profile_panel(user))
    console.print(Columns(
        [render_languages_panel(languages), render_highlights_panel(highlights)],
        equal=True, expand=True,
    ))
    if streaks is not None:
        console.print(render_streak_panel(streaks))
    if heatmap is not None:
        matrix, months = heatmap
        console.print(render_heatmap_panel(matrix, months))


# ---------------------------------------------------------------------- #
# Compare two users side-by-side (bonus feature)
# ---------------------------------------------------------------------- #
def render_compare(console: Console, a: dict[str, Any], b: dict[str, Any]) -> None:
    """Show a head-to-head table comparing two user reports."""
    t = Table(title="GitHub User Comparison", border_style="cyan", expand=True)
    t.add_column("Metric", style="bold")
    t.add_column(f"@{a['username']}", justify="right", style="green")
    t.add_column(f"@{b['username']}", justify="right", style="magenta")

    rows = [
        ("Public repos", a.get("public_repos", 0), b.get("public_repos", 0)),
        ("Followers", a.get("followers", 0), b.get("followers", 0)),
        ("Following", a.get("following", 0), b.get("following", 0)),
        ("Total stars", a["highlights"]["total_stars"], b["highlights"]["total_stars"]),
        ("Total forks", a["highlights"]["total_forks"], b["highlights"]["total_forks"]),
        ("Current streak", a["streaks"]["current"], b["streaks"]["current"]),
        ("Longest streak", a["streaks"]["longest"], b["streaks"]["longest"]),
        ("Contributions (1y)", a["streaks"]["total"], b["streaks"]["total"]),
        (
            "Top language",
            a["top_languages"][0]["language"] if a["top_languages"] else "—",
            b["top_languages"][0]["language"] if b["top_languages"] else "—",
        ),
    ]
    for metric, va, vb in rows:
        t.add_row(metric, str(va), str(vb))
    console.print(Align.center(t))
    