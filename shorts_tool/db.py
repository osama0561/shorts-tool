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
