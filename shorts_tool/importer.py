"""Local-file ingest: treat an existing mp4 on disk as a source video.

Runs when the user already has the video locally (downloaded from their
own YouTube Studio, pulled from Google Drive via ``gdown``, etc.).
Bypasses ``downloader.py`` and the entire YouTube bot-check dance.

Emits the same ``DownloadResult`` shape so the rest of the pipeline
treats local and downloaded videos identically.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from shorts_tool.downloader import DownloadResult


logger = logging.getLogger("shorts.importer")


def _probe_duration(video_path: Path) -> float:
    """Return the duration of a media file in seconds via ffprobe."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return float(out) if out else 0.0


def import_local(video_path: Path) -> DownloadResult:
    """Register a pre-existing video file and return metadata."""
    video_path = video_path.expanduser().resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Local video not found: {video_path}")

    duration = _probe_duration(video_path)
    result = DownloadResult(
        youtube_id=f"local::{video_path.stem}",
        title=video_path.stem,
        duration_sec=duration,
        path=video_path,
    )
    logger.info(
        "Imported local video: %s (%.1fs, %d bytes)",
        video_path.name, duration, video_path.stat().st_size,
    )
    return result
