"""CLI entrypoint.

Usage:
    python main.py <youtube_url-or-local-path>

Phase 1 behaviour:
    1. Load config from `.env`, set up logging, create the SQLite schema.
    2. Check disk space and abort if <5 GB free.
    3. Ingest the source video:
         - URL  → yt-dlp download into /inputs
         - path → validate + register (no download)
    4. Transcribe it locally with Whisper (Arabic, word-level timestamps).
    5. Write the transcript JSON to /working and record in SQLite.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from shorts_tool.config import PROJECT_ROOT, load_config
from shorts_tool.db import init_db, insert_transcript, set_video_status, upsert_video
from shorts_tool.downloader import download
from shorts_tool.importer import import_local
from shorts_tool.logging_setup import configure_logging
from shorts_tool.transcriber import transcribe


MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Turn a long Arabic video into vertical shorts."
    )
    p.add_argument(
        "source",
        help="YouTube URL, or path to a local video file already on disk",
    )
    p.add_argument(
        "--full",
        action="store_true",
        help="After transcription, also run Phase 2-4 (clip + cut + caption)",
    )
    p.add_argument(
        "--clips",
        type=int,
        default=10,
        help="Target clip count when --full is set (default 10)",
    )
    return p.parse_args(argv)


def _guard_disk_space(log: logging.Logger) -> None:
    """Abort the run if free disk space falls below MIN_FREE_BYTES."""
    free = shutil.disk_usage(PROJECT_ROOT).free
    free_gb = free / (1024 ** 3)
    if free < MIN_FREE_BYTES:
        raise RuntimeError(
            f"Aborting: only {free_gb:.1f} GB free at {PROJECT_ROOT} "
            f"(need >= {MIN_FREE_BYTES / 1024 ** 3:.0f} GB). "
            f"Run scripts/cleanup.sh or free space before retrying."
        )
    log.info("Disk guard OK: %.1f GB free", free_gb)


def _is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def run(source: str, full: bool = False, clips: int = 10) -> int:
    cfg = load_config()
    cfg.ensure_dirs()
    log = configure_logging(PROJECT_ROOT / "logs")
    init_db(cfg.db_path)

    _guard_disk_space(log)

    # ---------- 1. Ingest ----------
    if _is_url(source):
        log.info("Downloading %s", source)
        dl = download(
            source,
            cfg.inputs_dir,
            cookies_file=cfg.cookies_file,
            cookies_from_browser=cfg.cookies_from_browser,
        )
        log.info("Downloaded '%s' (%.0fs) → %s", dl.title, dl.duration_sec, dl.path)
        source_url = source
    else:
        dl = import_local(Path(source))
        log.info("Imported local '%s' (%.0fs) → %s",
                 dl.title, dl.duration_sec, dl.path)
        source_url = f"file://{dl.path}"

    video_id = upsert_video(
        cfg.db_path,
        youtube_url=source_url,
        youtube_id=dl.youtube_id,
        title=dl.title,
        duration_sec=dl.duration_sec,
        source_path=str(dl.path),
    )

    # ---------- 2. Transcribe ----------
    set_video_status(cfg.db_path, video_id, "transcribing")
    json_path, transcript = transcribe(
        video_path=dl.path,
        working_dir=cfg.working_dir,
        language="ar",
    )
    insert_transcript(
        cfg.db_path,
        video_id=video_id,
        language=transcript["language"],
        model=transcript["model"],
        json_path=str(json_path),
        word_count=transcript["word_count"],
    )
    set_video_status(cfg.db_path, video_id, "transcribed")

    # ---------- 3. Summary ----------
    words = transcript["words"]
    log.info("=" * 60)
    log.info("Video id:   %d", video_id)
    log.info("Source id:  %s", dl.youtube_id)
    log.info("Title:      %s", dl.title)
    log.info("Duration:   %.1fs", dl.duration_sec)
    log.info("Model:      %s", transcript["model"])
    log.info("Words:      %d", len(words))
    log.info("Transcript: %s", json_path)
    log.info("=" * 60)
    if words:
        preview = " ".join(w["word"] for w in words[:15])
        log.info("First 15 words: %s", preview)

    if full:
        # Import here so Phase 1-only runs don't pay the Gemini SDK cost.
        from process import run as process_run
        log.info("--full set; continuing into Phase 2-4")
        return process_run(video_id, clips)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return run(args.source, full=args.full, clips=args.clips)
    except KeyboardInterrupt:
        logging.getLogger("shorts").warning("Interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
