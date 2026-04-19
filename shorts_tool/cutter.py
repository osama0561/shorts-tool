"""Phase 3 — cut each selected clip from the source video and reframe
it to vertical 1080×1920 with a blurred-background, centered-speaker
composition.

One ffmpeg invocation per clip. Every call is prefixed with
``nice -n 10 ionice -c 3``.

Output naming: ``working/clips/<video_id>/clip_<idx>.mp4``
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TypedDict


logger = logging.getLogger("shorts.cutter")

_FFMPEG_NICE = ["nice", "-n", "10", "ionice", "-c", "3"]

# Opus-Clip-style composition: a blurred copy of the frame fills the
# 1080×1920 canvas, and the source frame (scaled to fit width) sits
# centred on top. Gives a cinematic look regardless of source aspect.
_VERTICAL_FILTER = (
    "[0:v]split=2[bg][fg];"
    "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920,gblur=sigma=24[bgblur];"
    "[fg]scale=1080:-2[fgscaled];"
    "[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2,format=yuv420p[outv]"
)


class CutResult(TypedDict):
    idx: int
    path: Path
    start_sec: float
    end_sec: float
    duration_sec: float


def cut_vertical(
    *,
    source_video: Path,
    out_dir: Path,
    idx: int,
    start_sec: float,
    end_sec: float,
) -> CutResult:
    """Cut [start_sec, end_sec) from source and reframe to 1080×1920."""
    if end_sec <= start_sec:
        raise ValueError(f"cut_vertical: end ({end_sec}) <= start ({start_sec})")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"clip_{idx:02d}.mp4"
    duration = end_sec - start_sec

    cmd = [
        *_FFMPEG_NICE,
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start_sec:.3f}",
        "-to", f"{end_sec:.3f}",
        "-i", str(source_video),
        "-filter_complex", _VERTICAL_FILTER,
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "160k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    logger.info(
        "Cutting clip %d: %.2fs → %.2fs (%.1fs) → %s",
        idx, start_sec, end_sec, duration, out_path.name,
    )
    subprocess.run(cmd, check=True, capture_output=True)

    return {
        "idx": idx,
        "path": out_path,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "duration_sec": round(duration, 2),
    }
