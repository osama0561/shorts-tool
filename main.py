"""CLI entrypoint.

Usage:
    python main.py <youtube_url>

Phase 1 behaviour:
    1. Load config from `.env` and create the SQLite schema if needed.
    2. Download the YouTube video with yt-dlp into /inputs
       (cookies may be required — see .env).
    3. Transcribe it locally with Whisper (Arabic, word-level timestamps).
    4. Write the transcript JSON to /working and record in SQLite.
"""

from __future__ import annotations

import argparse
import sys

from shorts_tool.config import load_config
from shorts_tool.db import init_db, insert_transcript, set_video_status, upsert_video
from shorts_tool.downloader import download
from shorts_tool.transcriber import transcribe


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Turn a long YouTube video into Arabic vertical shorts."
    )
    p.add_argument("url", help="YouTube URL to process")
    return p.parse_args(argv)


def run(youtube_url: str) -> int:
    cfg = load_config()
    cfg.ensure_dirs()
    init_db(cfg.db_path)

    # ---------- 1. Download ----------
    print(f"[main] Downloading {youtube_url}")
    dl = download(
        youtube_url,
        cfg.inputs_dir,
        cookies_file=cfg.cookies_file,
        cookies_from_browser=cfg.cookies_from_browser,
    )
    print(f"[main] Downloaded '{dl.title}' ({dl.duration_sec:.0f}s) → {dl.path}")

    video_id = upsert_video(
        cfg.db_path,
        youtube_url=youtube_url,
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
    print("\n" + "=" * 60)
    print(f"  Video id:    {video_id}")
    print(f"  YouTube id:  {dl.youtube_id}")
    print(f"  Title:       {dl.title}")
    print(f"  Duration:    {dl.duration_sec:.1f}s")
    print(f"  Model:       {transcript['model']}")
    print(f"  Words:       {len(words)}")
    print(f"  Transcript:  {json_path}")
    print(f"  Cost:        $0.00 (Whisper runs locally)")
    if words:
        print("\n  First 15 words:")
        for w in words[:15]:
            print(f"    [{w['start']:7.2f} → {w['end']:7.2f}]  {w['word']}")
    print("=" * 60)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return run(args.url)
    except KeyboardInterrupt:
        print("\n[main] Interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
