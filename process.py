"""Phase 2–4 driver: run against an already-transcribed video_id.

Usage:
    python process.py <video_id>

Does:
    2. Gemini picks clip windows from the transcript.
    3. ffmpeg cuts each window and reframes to 1080×1920 with blurred bg.
    4. Word-timed Arabic captions burned in.

The source video must exist on disk (recorded in ``videos.source_path``)
and a transcript row must exist for this ``video_id``. Stage 5 (logo
overlay) is deferred until a PNG is dropped in ``logos/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from shorts_tool.captioner import burn_captions
from shorts_tool.clip_selector import SelectorConfig, select_clips
from shorts_tool.config import PROJECT_ROOT, load_config
from shorts_tool.cutter import cut_vertical
from shorts_tool.db import (
    clear_clips,
    get_video,
    insert_clip,
    latest_transcript,
    list_clips,
    set_video_status,
    update_clip_paths,
)
from shorts_tool.logging_setup import configure_logging


def run(video_id: int, target_clips: int) -> int:
    cfg = load_config()
    cfg.ensure_dirs()
    log = configure_logging(PROJECT_ROOT / "logs")

    video = get_video(cfg.db_path, video_id)
    if video is None:
        raise SystemExit(f"No video with id={video_id}")
    source_path = Path(video["source_path"])
    if not source_path.is_file():
        raise SystemExit(f"Source video not on disk: {source_path}")

    transcript_row = latest_transcript(cfg.db_path, video_id)
    if transcript_row is None:
        raise SystemExit(f"No transcript for video_id={video_id}; run ingest first.")
    transcript_path = Path(transcript_row["json_path"])
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    words = transcript["words"]

    # ---------- Phase 2: select ----------
    log.info("Phase 2 — selecting clips via Gemini")
    set_video_status(cfg.db_path, video_id, "selecting")
    plans = select_clips(
        transcript_json=transcript_path,
        api_key=cfg.gemini_api_key,
        cfg=SelectorConfig(model=cfg.reasoning_model, target_count=target_clips),
    )

    clear_clips(cfg.db_path, video_id)
    for p in plans:
        insert_clip(
            cfg.db_path,
            video_id=video_id,
            idx=p["idx"],
            start_sec=p["start_sec"],
            end_sec=p["end_sec"],
            hook_summary=p["hook_summary"],
        )
    log.info("Saved %d clip plans to DB", len(plans))

    # ---------- Phase 3: cut + reframe ----------
    log.info("Phase 3 — cutting + reframing")
    set_video_status(cfg.db_path, video_id, "cutting")
    raw_dir = cfg.working_dir / "clips" / f"video_{video_id:03d}"
    for row in list_clips(cfg.db_path, video_id):
        cut = cut_vertical(
            source_video=source_path,
            out_dir=raw_dir,
            idx=row["idx"],
            start_sec=float(row["start_sec"]),
            end_sec=float(row["end_sec"]),
        )
        update_clip_paths(
            cfg.db_path, int(row["id"]),
            raw_path=str(cut["path"]),
            status="cut",
        )

    # ---------- Phase 4: captions ----------
    log.info("Phase 4 — burning captions")
    set_video_status(cfg.db_path, video_id, "captioning")
    out_dir = cfg.outputs_dir / f"video_{video_id:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    for row in list_clips(cfg.db_path, video_id):
        raw = Path(row["raw_path"])
        out_path = out_dir / f"short_{row['idx']:02d}.mp4"
        burn_captions(
            clip_video=raw,
            words=words,
            clip_start_sec=float(row["start_sec"]),
            clip_end_sec=float(row["end_sec"]),
            out_path=out_path,
        )
        update_clip_paths(
            cfg.db_path, int(row["id"]),
            captioned_path=str(out_path),
            final_path=str(out_path),   # no logo stage yet → final == captioned
            status="done",
        )

    set_video_status(cfg.db_path, video_id, "done")

    # ---------- Summary ----------
    log.info("=" * 60)
    log.info("Produced %d shorts under %s", len(plans), out_dir)
    for row in list_clips(cfg.db_path, video_id):
        log.info("  short_%02d  %6.1fs–%6.1fs  %s",
                 row["idx"], row["start_sec"], row["end_sec"],
                 row["hook_summary"] or "—")
    log.info("=" * 60)
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Phase 2-4 on a transcribed video.")
    p.add_argument("video_id", type=int, help="videos.id from the DB")
    p.add_argument("--clips", type=int, default=10,
                   help="Target number of clips (default 10)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return run(args.video_id, args.clips)
    except KeyboardInterrupt:
        logging.getLogger("shorts").warning("Interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
