# Stopwatch

A minimalist time-tracking widget for Ubuntu. Click a topic to declare what you're working on; the app records the transition and keeps a running clock. Everything is stored locally in a SQLite database.

![screenshot placeholder](docs/screenshot.png)

## Features

- One-click topic switching — the entire row is the click target
- Live per-topic time display (HH:MM, accumulated since midnight)
- Stays out of the way: float on top of other windows or minimize to the system tray
- Edit topics in place — rename, delete, or add new ones without restarting
- Crash-safe: a heartbeat mechanism ensures the database is never left in an inconsistent state
- No accounts, no sync, no telemetry — data lives in `~/.local/share/stopwatch/stopwatch.db`

## Requirements

- Ubuntu (tested on 22.04+)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

For system tray support on GNOME you also need the AppIndicator extension:

```bash
sudo apt install gnome-shell-extension-appindicator
gnome-extensions enable ubuntu-appindicators@ubuntu.com
# then log out and back in
```

## Running

```bash
uv sync
uv run stopwatch
```

## Usage

| Action | How |
|--------|-----|
| Switch topic | Click anywhere on a row |
| Minimize to tray | Click the window's × button |
| Restore from tray | Click the tray icon |
| Stay on top | `⋮` menu → Stay on top |
| Rename / delete topics | `✏` button → edit in place |
| Add a topic | `✏` button → type in the dashed row at the bottom |
| Quit cleanly | `⋮` menu → Quit, or right-click tray → Quit |

## Data

Transitions are recorded as append-only rows in a SQLite database:

```
~/.local/share/stopwatch/stopwatch.db
```

The `events` table has three columns: `id`, `topic`, `timestamp` (Unix seconds). Everything else — daily totals, session lengths — is computable from that log. You can query it directly with `sqlite3` or any SQLite tool.

## Design

See [DESIGN.md](DESIGN.md) for the full design document, including the data model, crash-safety mechanism, and rationale for technical choices.
