"""database.py — история запросов в SQLite (history.db)."""

import os
import json
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")


def _conn():
    return sqlite3.connect(DB)


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id          TEXT PRIMARY KEY,
                timestamp   TEXT,
                filename    TEXT,
                media       TEXT,
                elapsed     REAL,
                result_url  TEXT,
                stats       TEXT
            )""")


def add_record(rec):
    with _conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO requests
            (id, timestamp, filename, media, elapsed, result_url, stats)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rec["id"], rec["timestamp"], rec["filename"], rec["media"],
             rec["elapsed"], rec["result_url"],
             json.dumps(rec["stats"], ensure_ascii=False)))


def _row_to_dict(r):
    return {
        "id": r[0], "timestamp": r[1], "filename": r[2], "media": r[3],
        "elapsed": r[4], "result_url": r[5], "stats": json.loads(r[6]),
    }


def get_history(limit=50):
    with _conn() as c:
        rows = c.execute("""
            SELECT id, timestamp, filename, media, elapsed, result_url, stats
            FROM requests ORDER BY timestamp DESC LIMIT ?""", (limit,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_record(rec_id):
    with _conn() as c:
        r = c.execute("""
            SELECT id, timestamp, filename, media, elapsed, result_url, stats
            FROM requests WHERE id = ?""", (rec_id,)).fetchone()
    return _row_to_dict(r) if r else None
