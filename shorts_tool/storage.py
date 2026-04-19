"""Filesystem I/O abstraction.

Every stage that writes artifacts (transcripts, clip mp4s, ASS captions,
final branded shorts) goes through this module instead of touching the
filesystem directly. When we later swap local disk for S3 / Drive we
change only this file.

Callers so far: transcriber (JSON), cutter (mp4), captioner (ASS + mp4),
brander (mp4). More than two, so the abstraction earns its keep.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path


logger = logging.getLogger("shorts.storage")


def save_bytes(dest: Path, data: bytes) -> Path:
    """Atomically write bytes to dest; create parent dirs as needed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)
    logger.debug("Wrote %d bytes → %s", len(data), dest)
    return dest


def save_text(dest: Path, text: str, encoding: str = "utf-8") -> Path:
    """Atomically write text to dest."""
    return save_bytes(dest, text.encode(encoding))


def load_bytes(path: Path) -> bytes:
    """Read the whole file as bytes."""
    return path.read_bytes()


def load_text(path: Path, encoding: str = "utf-8") -> str:
    """Read the whole file as text."""
    return path.read_text(encoding=encoding)


def move_file(src: Path, dest: Path) -> Path:
    """Move (or rename) a file; create dest parent if missing."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return dest


def delete_file(path: Path) -> None:
    """Delete a file if it exists; silent no-op otherwise."""
    if path.exists():
        path.unlink()
        logger.debug("Deleted %s", path)
