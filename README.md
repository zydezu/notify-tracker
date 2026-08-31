# notify-tracker

A system to log desktop notifications (D-Bus `org.freedesktop.Notifications.Notify` call) to a local SQLite database, and provides a few scripts to browse and analyse the history.

Notifications are captured by eavesdropping on the session bus with `dbus-monitor`, so it works regardless of which notification daemon (eg: swaync or dunst) is actually displaying them.

## Requirements

- Linux with a D-Bus session bus and `dbus-monitor` installed
- Python 3.10+ and required packages

Use `pip`, or `uv` to install the required packages:

```sh
pip install -r requirements.txt
```

or

```sh
uv venv
uv install -r requirements.txt
```

NOTE: `tracker.py` and `tui.py` have no third-party dependencies.

## Components

| File | Description |
|---|---|
| `tracker.py` | Watches D-Bus and logs notifications to SQLite. Also prints per-app/sender counts (`--counts`). |
| `stats.py` | Prints daily volume, top apps, and top senders. |
| `sentiment.py` | Rough daily sentiment breakdown of message text using a built-in word/emoji lexicon. |
| `tui.py` | Curses TUI for browsing/filtering logged notifications live. |

The database lives at `~/.local/share/notify-tracker/notifications.db` and is created automatically on the first run.

## Usage

Start logging:

```sh
python3 tracker.py
```

Show notification counts by app/sender:

```sh
python3 tracker.py --counts [app-filter]
```

Volume stats (per day, top apps, top senders):

```sh
python3 stats.py [app-filter]
```

Daily sentiment trend:

```sh
python3 sentiment.py [app-filter]
```

Browse data in a terminal:

```sh
python3 tui.py [app-filter]
```

In the TUI: `j`/`k` or arrow keys to scroll, `g`/`G` for top/bottom,
`/` to filter, `c` to clear the filter, `q` to quit.

## Running as a service

`notify-tracker.service` is a systemd user unit that runs `tracker.py`
continuously. Install it with:

```sh
mkdir -p ~/.config/systemd/user
cp notify-tracker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now notify-tracker.service
```

The unit invokes `/usr/bin/python3` directly (no virtualenv), so make sure `rich` is available to that interpreter, e.g:

```sh
pacman -S python-rich
```
