"""SQLite persistence layer.

Three tables mirror the pipeline stages:

    videos       — one row per ingested YouTube URL
    transcripts  — one row per transcript run (linked to a video)
    clips        — one row per extracted short (linked to a video)

Schema is created lazily by `init_db()`. No migrations yet — the tool is
still pre-v1, so we just version via additive columns when needed.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_url    TEXT    NOT NULL,
    youtube_id     TEXT    UNIQUE,
    title          TEXT,
    duration_sec   REAL,
    source_path    TEXT,           -- where the downloaded file lives on disk
    status         TEXT    NOT NULL DEFAULT 'downloaded',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transcripts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id       INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    language       TEXT    NOT NULL DEFAULT 'ar',
    model          TEXT    NOT NULL,
    json_path      TEXT    NOT NULL,   -- path to the full word-level JSON
    word_count     INTEGER,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clips (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id       INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    idx            INTEGER NOT NULL,    -- ordering within the parent video
    start_sec      REAL    NOT NULL,
    end_sec        REAL    NOT NULL,
    hook_summary   TEXT,
    raw_path       TEXT,                -- uncaptioned 1080x1920 cut
    captioned_path TEXT,                -- after ASS burn-in
    final_path     TEXT,                -- after logo overlays, in /outputs
    status         TEXT    NOT NULL DEFAULT 'planned',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(video_id, idx)
);

CREATE INDEX IF NOT EXISTS idx_transcripts_video ON transcripts(video_id);
CREATE INDEX IF NOT EXISTS idx_clips_video ON clips(video_id);
"""


def init_db(db_path: Path) -> None:
    """Create tables if they don't already exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Context-managed connection with foreign keys on and row factory set."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- Videos ----------

def upsert_video(
    db_path: Path,
    *,
    youtube_url: str,
    youtube_id: str | None,
    title: str | None,
    duration_sec: float | None,
    source_path: str | None,
) -> int:
    """Insert or update a video row keyed on youtube_id; return its id."""
    with connect(db_path) as conn:
        if youtube_id:
            row = conn.execute(
                "SELECT id FROM videos WHERE youtube_id = ?", (youtube_id,)
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE videos
                       SET youtube_url = ?, title = ?, duration_sec = ?,
                           source_path = ?, updated_at = datetime('now')
                       WHERE id = ?""",
                    (youtube_url, title, duration_sec, source_path, row["id"]),
                )
                return int(row["id"])

        cur = conn.execute(
            """INSERT INTO videos
               (youtube_url, youtube_id, title, duration_sec, source_path)
               VALUES (?, ?, ?, ?, ?)""",
            (youtube_url, youtube_id, title, duration_sec, source_path),
        )
        return int(cur.lastrowid)


def set_video_status(db_path: Path, video_id: int, status: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE videos SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, video_id),
        )


# ---------- Transcripts ----------

def insert_transcript(
    db_path: Path,
    *,
    video_id: int,
    language: str,
    model: str,
    json_path: str,
    word_count: int,
) -> int:
    with connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO transcripts
               (video_id, language, model, json_path, word_count)
               VALUES (?, ?, ?, ?, ?)""",
            (video_id, language, model, json_path, word_count),
        )
        return int(cur.lastrowid)


def latest_transcript(db_path: Path, video_id: int) -> sqlite3.Row | None:
    """Return the most recent transcript row for a video, or None."""
    with connect(db_path) as conn:
        return conn.execute(
            """SELECT * FROM transcripts
               WHERE video_id = ?
               ORDER BY id DESC LIMIT 1""",
            (video_id,),
        ).fetchone()


def get_video(db_path: Path, video_id: int) -> sqlite3.Row | None:
    """Return a video row by id, or None."""
    with connect(db_path) as conn:
        return conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()


# ---------- Clips ----------

def insert_clip(
    db_path: Path,
    *,
    video_id: int,
    idx: int,
    start_sec: float,
    end_sec: float,
    hook_summary: str | None,
) -> int:
    """Insert a planned clip; idempotent per (video_id, idx)."""
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO clips (video_id, idx, start_sec, end_sec, hook_summary)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(video_id, idx) DO UPDATE SET
                   start_sec = excluded.start_sec,
                   end_sec = excluded.end_sec,
                   hook_summary = excluded.hook_summary""",
            (video_id, idx, start_sec, end_sec, hook_summary),
        )
        row = conn.execute(
            "SELECT id FROM clips WHERE video_id = ? AND idx = ?",
            (video_id, idx),
        ).fetchone()
        return int(row["id"])


def update_clip_paths(
    db_path: Path,
    clip_id: int,
    *,
    raw_path: str | None = None,
    captioned_path: str | None = None,
    final_path: str | None = None,
    status: str | None = None,
) -> None:
    """Update any subset of a clip's output paths and/or status."""
    sets: list[str] = []
    params: list = []
    if raw_path is not None:
        sets.append("raw_path = ?"); params.append(raw_path)
    if captioned_path is not None:
        sets.append("captioned_path = ?"); params.append(captioned_path)
    if final_path is not None:
        sets.append("final_path = ?"); params.append(final_path)
    if status is not None:
        sets.append("status = ?"); params.append(status)
    if not sets:
        return
    params.append(clip_id)
    with connect(db_path) as conn:
        conn.execute(f"UPDATE clips SET {', '.join(sets)} WHERE id = ?", params)


def list_clips(db_path: Path, video_id: int) -> list[sqlite3.Row]:
    """Return all clips for a video, ordered by idx."""
    with connect(db_path) as conn:
        return list(conn.execute(
            "SELECT * FROM clips WHERE video_id = ? ORDER BY idx", (video_id,)
        ).fetchall())


def clear_clips(db_path: Path, video_id: int) -> int:
    """Delete all clip rows for a video; returns count deleted."""
    with connect(db_path) as conn:
        cur = conn.execute("DELETE FROM clips WHERE video_id = ?", (video_id,))
        return cur.rowcount
