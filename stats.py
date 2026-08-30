#!/usr/bin/env python3
"""Notification stats: daily volume, top apps, top senders.

Reads the same SQLite DB that tracker.py writes to and prints three
breakdowns of how many notifications came in: per day, per app, and per
sender (i.e. the person/channel, not just the app).
"""
import re
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table

from tracker import init_db

TOP_N = 15
TOP_PER_DAY = 5
BAR_WIDTH = 20

console = Console()

# Discord reply notifications name the sender "X replying to Y", which would
# otherwise fragment a single person into two separate senders.
REPLYING_TO_RE = re.compile(r"^(.*?) replying to .+$", re.IGNORECASE)


def local_date(iso_ts: str) -> str:
    return datetime.fromisoformat(iso_ts).astimezone().strftime("%Y-%m-%d")


def normalize_sender(sender: str) -> str:
    match = REPLYING_TO_RE.match(sender)
    return match.group(1) if match else sender


def bar(n: int, max_n: int) -> str:
    filled = round(n / max_n * BAR_WIDTH) if max_n else 0
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def print_count_table(title: str, rows: list[tuple[str, int]], label_header: str) -> None:
    table = Table(title=title, title_style="bold", header_style="bold")
    table.add_column(label_header, style="cyan", no_wrap=True)
    table.add_column("count", justify="right")
    table.add_column("")

    if not rows:
        console.print(table)
        console.print("  (none)")
        return

    max_n = max(n for _, n in rows)
    for label, n in rows:
        table.add_row(label, str(n), f"[magenta]{bar(n, max_n)}[/magenta]")
    console.print(table)


def print_daily_top_table(title: str, by_day_group: dict[str, dict[str, int]], top_n: int) -> None:
    table = Table(title=title, title_style="bold", header_style="bold")
    table.add_column("date", style="cyan", no_wrap=True)
    table.add_column("sender", style="cyan", no_wrap=True)
    table.add_column("count", justify="right")
    table.add_column("")

    if not by_day_group:
        console.print(table)
        console.print("  (none)")
        return

    for day in sorted(by_day_group):
        top = sorted(by_day_group[day].items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        max_n = top[0][1]
        for i, (label, n) in enumerate(top):
            table.add_row(day if i == 0 else "", label, str(n), f"[magenta]{bar(n, max_n)}[/magenta]")
        table.add_section()
    console.print(table)


def analyze(app_filter: str | None = None) -> None:
    conn = init_db()
    if app_filter:
        like = f"%{app_filter}%"
        rows = conn.execute(
            "SELECT app_name, sender, received_at FROM notifications "
            "WHERE app_name LIKE ? OR sender LIKE ?",
            (like, like),
        ).fetchall()
    else:
        rows = conn.execute("SELECT app_name, sender, received_at FROM notifications").fetchall()

    if not rows:
        console.print("No notifications logged yet.")
        return

    by_day: dict[str, int] = {}
    by_app: dict[str, int] = {}
    by_sender: dict[str, int] = {}
    by_day_sender: dict[str, dict[str, int]] = {}

    for app_name, sender, received_at in rows:
        day = local_date(received_at)
        by_day[day] = by_day.get(day, 0) + 1
        by_app[app_name] = by_app.get(app_name, 0) + 1
        sender = normalize_sender(sender)
        by_sender[sender] = by_sender.get(sender, 0) + 1
        day_senders = by_day_sender.setdefault(day, {})
        day_senders[sender] = day_senders.get(sender, 0) + 1

    console.print(f"[bold]Total notifications:[/bold] {len(rows)}\n")

    daily_rows = sorted(by_day.items())
    print_count_table("Per day", daily_rows, "date")

    top_apps = sorted(by_app.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
    print_count_table(f"Top {TOP_N} apps", top_apps, "app")

    top_senders = sorted(by_sender.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
    print_count_table(f"Top {TOP_N} senders", top_senders, "sender")

    print_daily_top_table(f"Daily top {TOP_PER_DAY} senders", by_day_sender, TOP_PER_DAY)


if __name__ == "__main__":
    analyze(sys.argv[1] if len(sys.argv) > 1 else None)
