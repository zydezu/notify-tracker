#!/usr/bin/env python3
"""Simple curses TUI for browsing tracked notifications.

Reads the same SQLite DB that tracker.py writes to, and auto-refreshes
so notifications logged while the TUI is open show up live.
"""
import curses
import sys
from datetime import datetime

from tracker import init_db

REFRESH_MS = 2000
FETCH_LIMIT = 2000


def fetch_rows(conn, app_filter):
    if app_filter:
        like = f"%{app_filter}%"
        return conn.execute(
            "SELECT app_name, sender, message, received_at FROM notifications "
            "WHERE app_name LIKE ? OR sender LIKE ? ORDER BY id DESC LIMIT ?",
            (like, like, FETCH_LIMIT),
        ).fetchall()
    return conn.execute(
        "SELECT app_name, sender, message, received_at FROM notifications "
        "ORDER BY id DESC LIMIT ?",
        (FETCH_LIMIT,),
    ).fetchall()


def local_time(iso_ts: str) -> str:
    return datetime.fromisoformat(iso_ts).astimezone().strftime("%H:%M:%S")


def draw_row(stdscr, y, width, app, sender, message, ts):
    stdscr.addnstr(y, 0, f"{local_time(ts)}  ", width)
    col = 11

    app_str = f"{app[:14]:<14} "
    stdscr.addnstr(y, col, app_str, max(0, width - col), curses.color_pair(1))
    col += len(app_str)

    sender_str = f"{sender[:28]:<28} "
    stdscr.addnstr(y, col, sender_str, max(0, width - col), curses.color_pair(2))
    col += len(sender_str)

    stdscr.addnstr(y, col, message.replace("\n", " "), max(0, width - col))


def main(stdscr, initial_filter=None):
    curses.curs_set(0)
    try:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
    except curses.error:
        pass
    stdscr.timeout(REFRESH_MS)

    conn = init_db()
    offset = 0
    app_filter = initial_filter
    filtering = False
    filter_buf = ""

    while True:
        rows = fetch_rows(conn, app_filter)
        height, width = stdscr.getmaxyx()
        list_height = max(1, height - 2)

        max_offset = max(0, len(rows) - list_height)
        offset = min(offset, max_offset)

        stdscr.erase()
        title = f" notify-tracker — {len(rows)} shown"
        if app_filter:
            title += f"  (filter: {app_filter})"
        stdscr.addnstr(0, 0, title.ljust(width), width, curses.A_REVERSE)

        for i in range(list_height):
            idx = offset + i
            if idx >= len(rows):
                break
            app, sender, message, ts = rows[idx]
            draw_row(stdscr, i + 1, width, app, sender, message, ts)

        if filtering:
            footer = f"filter> {filter_buf}"
        else:
            footer = "/:filter  c:clear filter  j/k:scroll  g/G:top/bottom  q:quit"
        try:
            # Writing the very last cell of the screen raises in some terminals; harmless.
            stdscr.addnstr(height - 1, 0, footer.ljust(width), width - 1, curses.A_REVERSE)
        except curses.error:
            pass

        stdscr.refresh()
        ch = stdscr.getch()

        if filtering:
            if ch in (10, 13):
                app_filter = filter_buf or None
                filtering = False
                offset = 0
            elif ch == 27:
                filtering = False
                filter_buf = ""
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                filter_buf = filter_buf[:-1]
            elif 32 <= ch < 127:
                filter_buf += chr(ch)
            continue

        if ch == -1:
            continue
        elif ch in (ord('q'), 27):
            break
        elif ch in (ord('j'), curses.KEY_DOWN):
            offset = min(offset + 1, max_offset)
        elif ch in (ord('k'), curses.KEY_UP):
            offset = max(offset - 1, 0)
        elif ch == curses.KEY_NPAGE:
            offset = min(offset + list_height, max_offset)
        elif ch == curses.KEY_PPAGE:
            offset = max(offset - list_height, 0)
        elif ch in (ord('g'), curses.KEY_HOME):
            offset = 0
        elif ch in (ord('G'), curses.KEY_END):
            offset = max_offset
        elif ch == ord('/'):
            filtering = True
            filter_buf = app_filter or ""
        elif ch == ord('c'):
            app_filter = None
            offset = 0


if __name__ == "__main__":
    curses.wrapper(main, sys.argv[1] if len(sys.argv) > 1 else None)
