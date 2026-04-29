# Stopwatch — Design Document

## User Story

> I want a lightweight background tool that helps me stay honest about where my
> time goes during the day. I don't need reports or charts — I just need a quick
> way to declare "I am now working on X" and have the tool remember that. At the
> end of the day (or whenever I'm curious) I can open the database and see the
> record for myself.

The tool targets a single user on a personal Linux desktop. It must be low
enough friction to use continuously: if it ever feels like overhead to switch
topics, it will be ignored.

---

## Goals

1. **Minimal friction.** Switching topics is a single click anywhere on a row.
2. **Always accessible.** The window can float on top of other apps, or retreat
   to the system tray when not needed.
3. **Honest accounting.** The data model is immutable append-only events; no
   time is silently lost or fabricated.
4. **Crash-safe.** If the process dies unexpectedly the database is left in a
   coherent state via a heartbeat mechanism.
5. **User-controlled topics.** Topics can be added, renamed, or deleted from
   within the UI without restarting the application.

## Non-goals (for now)

- Reports, charts, exports, or summaries (the SQLite file is the report).
- Multi-device sync or cloud storage.
- Pomodoro timers, goals, or notifications.
- Richer time visualizations ("brick" style, sparklines, etc.) — noted as a
  possible future addition.

---

## Data Model

### Philosophy

Time is recorded as a sequence of *transition events*. Each event says "at
timestamp T the user switched to topic X." The duration spent on any topic is
always *derived* — it is the gap between two consecutive events. This means:

- The database is append-only and never needs to be corrected retroactively
  under normal operation.
- Derived quantities (daily totals, session lengths) can always be recomputed
  from first principles.
- A bug in the display layer can never corrupt the underlying record.

### Schema

```sql
-- ordered list of user-defined time buckets
CREATE TABLE topics (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL UNIQUE,
    position INTEGER NOT NULL,         -- display order
    is_idle  INTEGER NOT NULL DEFAULT 0  -- exactly one row is the default
);

-- append-only transition log
CREATE TABLE events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    topic     TEXT    NOT NULL,
    timestamp INTEGER NOT NULL         -- Unix epoch seconds
);

-- small key/value store for app state
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
    -- used for: last_heartbeat
);
```

The database lives at `~/.local/share/stopwatch/stopwatch.db`.

### Idle topic

One topic is designated `is_idle=1`. It represents "not working on anything
billable" and serves as the application's neutral/default state. On first run
the app creates a topic named "Idle" with this flag. The idle topic cannot be
deleted (only renamed).

---

## Crash Safety

### The problem

If the process is killed (power loss, OOM, `kill -9`) the last transition event
in the database is left open. Naively computing totals would credit that topic
with time all the way up to the next query — possibly hours or days later.

### Solution: heartbeat + recovery

**While running:** a `QTimer` fires every 30 seconds and writes
`last_heartbeat = <unix_ts>` into the `meta` table.

**On startup:** `recover_if_crashed()` checks:

1. Is the last event's topic the idle topic? If yes, the previous session closed
   cleanly — nothing to do.
2. Is the last heartbeat timestamp within the last 60 seconds? If yes, the app
   was just restarted normally — nothing to do.
3. Otherwise (heartbeat is stale or absent): insert a synthetic transition to
   Idle at the heartbeat timestamp. This caps the open interval at the last
   known-alive moment.

**On clean quit:** the app logs a transition to Idle before exiting, making
recovery unnecessary on the next start.

The 60-second threshold is intentionally generous; a normal restart takes well
under 5 seconds.

---

## UI Design

### Window

A narrow floating rectangle (~260 × 320 px). The window has standard OS
decorations so it can be dragged and resized. Two modes:

| Mode | Behavior |
|------|----------|
| Floating | Stays visible alongside other windows; "Stay on top" option pins it above everything else |
| Tray | Window is hidden; single-click the tray icon toggles visibility |

Closing the window (× button) hides to tray rather than quitting. "Quit" in the
tray menu or the `⋮` header menu performs a clean shutdown.

On restart the window always opens in the foreground showing the Idle state,
regardless of what was active when the app was last closed or crashed.

### Topic rows

Each row occupies the full widget width and is 38 px tall. The entire row
surface is the click target (not just the text label) to make selection easy.

**Normal mode** — click to activate:

```
 ┌─────────────────────────────────────┐
 │  Deep Work                   01:35  │  ← active: bold, colored bg + border
 │  Meetings                    00:45  │  ← inactive
 │  Admin                       00:12  │
 │  Idle                        00:00  │
 └─────────────────────────────────────┘
```

Active row: filled background (#1a3050), blue border (#3a7bd5), bold white text,
accent-colored time.  
Inactive rows: transparent background, soft hover highlight.

**Edit mode** — toggled with the ✏ button in the header:

- Each row's label becomes an editable text field (rename in place).
- Non-idle rows gain a × delete button on the right.
- A dashed "Add topic…" row appears at the bottom; pressing Enter adds and
  immediately shows the new topic.
- The active topic continues running while topics are being edited.

### Header

```
 Stopwatch                       ✏  ⋮
```

- `✏` toggles edit mode (stays visually "pressed" while active).
- `⋮` opens a small menu: **Stay on top** (checkable), **Quit**.

### Time display

Each row shows `HH:MM` (hours and minutes) accumulated for the **current
calendar day**, counting from midnight. If a session was active at midnight it
is credited from 00:00 onward. The active topic's counter updates every second
in the UI without any database writes; only transitions are persisted.

---

## Architecture

```
main.py          Entry point: init DB, recover, launch QApplication + MainWindow
db.py            All SQLite logic — schema, topic CRUD, event log, heartbeat,
                 crash recovery, daily totals
ui.py            QWidget MainWindow, TopicRow, AddTopicRow, system tray
```

### In-memory time state (MainWindow)

The window keeps two variables to drive the live counter without polling the DB:

| Variable | Type | Meaning |
|----------|------|---------|
| `_active` | `str` | Name of the currently active topic |
| `_active_since` | `float` | `time.time()` when that topic became active |
| `_base_totals` | `dict[str, float]` | Seconds accumulated before the current session |

Displayed seconds for any topic:
- **Active:** `_base_totals[topic] + (now - _active_since)`
- **Inactive:** `_base_totals[topic]`

On each topic switch `_base_totals[old_topic]` is incremented by the elapsed
time, `_active` and `_active_since` are updated, and a single `INSERT` is
written to `events`.

---

## Technical Choices

| Choice | Rationale |
|--------|-----------|
| **Python** | Fast iteration, large stdlib, good Qt bindings |
| **PySide6** | Official Qt6 Python binding (LGPL); `QSystemTrayIcon` and all needed widgets are built in |
| **SQLite** | Zero-config, single-file, perfectly adequate for append-only event logs at this scale |
| **Append-only events** | Simpler than storing pre-computed durations; enables recomputation and retrospective correction |
| **No ORM** | The schema is trivial; raw `sqlite3` keeps the dependency footprint minimal |
| **Three-file layout** | `db.py` is pure logic with no Qt imports, making it independently testable |

### Ubuntu / GNOME tray note

`QSystemTrayIcon` on GNOME requires a shell extension to display tray icons.
Install with:

```bash
sudo apt install gnome-shell-extension-appindicator
# then enable via GNOME Extensions app or:
gnome-extensions enable ubuntu-appindicators@ubuntu.com
```

If the tray is unavailable, the app falls back gracefully: the window behaves
normally and the × button closes via clean quit rather than minimizing to tray.

### Running

```bash
pip install PySide6
python main.py
```

No other dependencies are required.
