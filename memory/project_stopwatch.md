---
name: Stopwatch project overview
description: Time-tracking widget for Ubuntu — Python/PySide6/SQLite, minimalist floating window
type: project
---

A minimalist desktop time-tracking widget. User clicks a topic row to declare current focus; the app records transition events to a local SQLite DB.

**Why:** Personal productivity tracking with zero friction. No reports or sync needed — the SQLite file is the record.

**How to apply:** When suggesting features or changes, keep it minimal and low-friction. The user explicitly wants simplicity over richness.

**Stack:** Python 3, PySide6, SQLite (raw sqlite3, no ORM), three files: main.py / db.py / ui.py.

**Key design decisions:**
- Append-only `events` table (topic, timestamp); durations always derived
- `is_idle=1` topic is the default/start state; one always exists, can't be deleted
- Heartbeat every 30s → crash recovery inserts synthetic Idle event at last heartbeat
- App always starts in Idle (logs Idle transition on startup if DB shows otherwise)
- Window X → hide to tray; Quit (tray/menu) → log Idle + exit
- Edit mode toggle (✏ button): rows become text inputs; × delete; dashed "Add topic…" row at bottom
- Time display: HH:MM accumulated since midnight, live counter in memory (no per-second DB writes)

**Location:** /home/mkayser/work/stopwatch/
