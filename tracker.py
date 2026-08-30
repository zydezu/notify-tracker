#!/usr/bin/env python3
"""Watches D-Bus for all desktop notifications and logs them to SQLite.

Notifications arrive as org.freedesktop.Notifications.Notify calls, which
swaync (or any notification daemon) receives and displays. This eavesdrops
on the session bus for those calls instead of going through swaync, since
swaync-client only exposes counts, not notification content.
"""
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "notify-tracker" / "notifications.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT NOT NULL,
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    raw_summary TEXT NOT NULL,
    raw_body TEXT NOT NULL,
    received_at TEXT NOT NULL
);
"""

# Top-level Notify() args are indented exactly 3 spaces by dbus-monitor;
# nested array/dict entries (actions, hints) are indented further, so this
# only picks up app_name, app_icon, summary, body in order.
TOP_LEVEL_STRING = re.compile(r'^   string "(.*)"$')

# Discord's server-channel notifications format the body as
# "Username: message text". DM notifications just have the raw message as
# the body, with the sender in the summary instead. This heuristic is
# Discord-specific and may need adjusting if it changes its notification
# format; other apps just get summary/body stored as-is.
SENDER_PREFIX = re.compile(r'^([^\s:][^:]{0,60}): (.*)$', re.S)


def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def split_sender(app_name: str, summary: str, body: str) -> tuple[str, str]:
    if "discord" in app_name.lower():
        match = SENDER_PREFIX.match(body)
        if match:
            return match.group(1), match.group(2)
    return summary, body


def watch() -> None:
    conn = init_db()
    print(f"Logging all notifications to {DB_PATH}", flush=True)

    cmd = [
        "dbus-monitor", "--session",
        "interface='org.freedesktop.Notifications',member='Notify'",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, bufsize=1)

    in_block = False
    top_strings: list[str] = []

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")

        if line.startswith("method call") and "member=Notify" in line:
            in_block = True
            top_strings = []
            continue

        if line.startswith(("method call", "signal", "error")):
            in_block = False
            top_strings = []
            continue

        if not in_block:
            continue

        match = TOP_LEVEL_STRING.match(line)
        if match:
            top_strings.append(match.group(1))

        if len(top_strings) >= 4:
            app_name, _app_icon, summary, body = top_strings[:4]
            in_block = False
            top_strings = []

            sender, message = split_sender(app_name, summary, body)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO notifications (app_name, sender, message, raw_summary, raw_body, received_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (app_name, sender, message, summary, body, now),
            )
            conn.commit()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ({app_name}) {sender}: {message}", flush=True)


def show_counts(app_filter: str | None = None) -> None:
    conn = init_db()
    if app_filter:
        rows = conn.execute(
            "SELECT app_name, sender, COUNT(*) AS n FROM notifications "
            "WHERE app_name LIKE ? GROUP BY app_name, sender ORDER BY n DESC",
            (f"%{app_filter}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT app_name, sender, COUNT(*) AS n FROM notifications "
            "GROUP BY app_name, sender ORDER BY n DESC"
        ).fetchall()
    if not rows:
        print("No notifications logged yet.")
        return
    app_width = max(len(app) for app, _, _ in rows)
    sender_width = max(len(sender) for _, sender, _ in rows)
    for app, sender, n in rows:
        print(f"{n:5d}  {app.ljust(app_width)}  {sender.ljust(sender_width)}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--counts", "-c"):
        show_counts(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        try:
            watch()
        except KeyboardInterrupt:
            pass
