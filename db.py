import sqlite3
import time
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path.home() / '.local' / 'share' / 'stopwatch' / 'stopwatch.db'


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS topics (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT    NOT NULL UNIQUE,
                position INTEGER NOT NULL,
                is_idle  INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS events (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                topic     TEXT    NOT NULL,
                timestamp INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        if conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO topics (name, position, is_idle) VALUES ('Idle', 0, 1)"
            )


# ---------- topic CRUD ----------

def get_topics():
    """Returns list of (name, is_idle) ordered by position."""
    with _connect() as conn:
        return conn.execute(
            "SELECT name, is_idle FROM topics ORDER BY position"
        ).fetchall()


def get_idle_name():
    with _connect() as conn:
        row = conn.execute(
            "SELECT name FROM topics WHERE is_idle=1 LIMIT 1"
        ).fetchone()
        return row[0] if row else 'Idle'


def add_topic(name):
    with _connect() as conn:
        pos = conn.execute(
            "SELECT COALESCE(MAX(position)+1, 1) FROM topics"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO topics (name, position, is_idle) VALUES (?,?,0)", (name, pos)
        )


def rename_topic(old, new):
    with _connect() as conn:
        conn.execute("UPDATE topics SET name=? WHERE name=?", (new, old))
        conn.execute("UPDATE events SET topic=? WHERE topic=?", (new, old))


def delete_topic(name):
    with _connect() as conn:
        conn.execute("DELETE FROM topics WHERE name=? AND is_idle=0", (name,))


# ---------- events ----------

def log_transition(topic):
    ts = int(time.time())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO events (topic, timestamp) VALUES (?,?)", (topic, ts)
        )
    return ts


def get_active_topic():
    """Most recent event's topic, or None if no events."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT topic FROM events ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None


# ---------- heartbeat & crash recovery ----------

def update_heartbeat():
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key,value) VALUES ('last_heartbeat',?)",
            (str(int(time.time())),)
        )


def recover_if_crashed():
    """
    On startup: if the last logged topic is not Idle and the heartbeat is stale
    (>60 s ago), insert a synthetic Idle event at the heartbeat timestamp so the
    database never implies unbounded work after a crash.
    """
    with _connect() as conn:
        last = conn.execute(
            "SELECT topic, timestamp FROM events ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if last is None:
            return

        topic, event_ts = last
        idle = conn.execute(
            "SELECT name FROM topics WHERE is_idle=1 LIMIT 1"
        ).fetchone()
        idle_name = idle[0] if idle else 'Idle'
        if topic == idle_name:
            return

        hb_row = conn.execute(
            "SELECT value FROM meta WHERE key='last_heartbeat'"
        ).fetchone()
        last_hb = int(hb_row[0]) if hb_row else None
        now = int(time.time())

        if last_hb is None or (now - last_hb) > 60:
            # Use last heartbeat as the close time; fall back to event_ts + 30s
            recovery_ts = (last_hb if last_hb and last_hb > event_ts
                           else event_ts + 30)
            conn.execute(
                "INSERT INTO events (topic, timestamp) VALUES (?,?)",
                (idle_name, recovery_ts)
            )


# ---------- time totals ----------

def get_today_totals():
    """
    Returns {topic_name: seconds} summed from midnight today until now.
    If a session began before midnight and hasn't ended, it is credited from
    midnight onward.
    """
    today_start = int(datetime.combine(date.today(), datetime.min.time()).timestamp())
    now = int(time.time())

    with _connect() as conn:
        today_events = conn.execute(
            "SELECT topic, timestamp FROM events "
            "WHERE timestamp >= ? ORDER BY timestamp",
            (today_start,)
        ).fetchall()

        # Check whether there is an open session that started before midnight
        prev = conn.execute(
            "SELECT topic FROM events WHERE timestamp < ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (today_start,)
        ).fetchone()

    idle_name = get_idle_name()
    effective = []
    if prev and prev[0] != idle_name:
        effective.append((prev[0], today_start))
    effective.extend(today_events)

    if not effective:
        return {}

    totals = {}
    for i, (topic, ts) in enumerate(effective):
        end = effective[i + 1][1] if i + 1 < len(effective) else now
        totals[topic] = totals.get(topic, 0) + max(0, end - ts)
    return totals
