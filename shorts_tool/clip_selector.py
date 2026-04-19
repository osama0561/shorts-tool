"""Phase 2 — Gemini picks short-worthy moments from a transcript.

Inputs:  transcript JSON produced by transcriber.py (word-level).
Outputs: a list of ClipPlan dicts with start_sec/end_sec/hook_summary.

The word-level transcript is stitched back into sentence-ish chunks
with their timestamps so Gemini can reason over plain text while we
retain the mapping back to seconds. We ask Gemini for strict JSON.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from google import genai
from google.genai import types


logger = logging.getLogger("shorts.clip_selector")


class ClipPlan(TypedDict):
    idx: int
    start_sec: float
    end_sec: float
    hook_summary: str


@dataclass(frozen=True)
class SelectorConfig:
    model: str
    min_len_sec: float = 30.0
    max_len_sec: float = 90.0
    target_count: int = 10


# --------------------------------------------------------------------- #
# Transcript → compact "timed paragraphs" feed for Gemini.
# --------------------------------------------------------------------- #

_SENTENCE_BREAK = re.compile(r"[\.؟\?!…]+\s*$")


def _group_into_sentences(
    words: list[dict], max_gap_sec: float = 1.2
) -> list[dict]:
    """Group word-level tokens into sentence-ish chunks with timestamps."""
    chunks: list[dict] = []
    buf: list[dict] = []
    for w in words:
        if buf and (w["start"] - buf[-1]["end"]) > max_gap_sec:
            chunks.append(_flush(buf)); buf = []
        buf.append(w)
        if _SENTENCE_BREAK.search(w["word"]):
            chunks.append(_flush(buf)); buf = []
    if buf:
        chunks.append(_flush(buf))
    return chunks


def _flush(buf: list[dict]) -> dict:
    return {
        "start": round(float(buf[0]["start"]), 2),
        "end": round(float(buf[-1]["end"]), 2),
        "text": " ".join(w["word"] for w in buf).strip(),
    }


def _render_feed(chunks: list[dict]) -> str:
    """Render the sentence chunks as a timestamped plain-text feed."""
    lines = []
    for c in chunks:
        lines.append(f"[{c['start']:7.2f} – {c['end']:7.2f}] {c['text']}")
    return "\n".join(lines)


# --------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------- #

_SYSTEM = """\
You select moments from a long-form Arabic video that will work as
standalone vertical short-form videos (TikTok / Reels / YouTube
Shorts).

Rules — follow them exactly:
1. Each moment must be a complete thought: a full idea, story, punch,
   answer, or insight. The viewer must understand it with ZERO context
   from before or after.
2. Each moment must start with a strong hook — a question, a bold
   claim, a number, a promise, or a contrarian statement. Never start
   mid-sentence.
3. Each moment must end on a natural beat — a conclusion, a resolution,
   a call to action. Never cut off mid-word or mid-argument.
4. Prefer moments that include a concrete tip, a mini-story with
   payoff, a counterintuitive claim, or a specific number / name.
5. Keep lengths between {min_len} and {max_len} seconds. Aim for the
   shorter side unless the story needs the length.
6. Return non-overlapping moments, ordered by start time.
7. Return a JSON object with one key: "clips". Each clip is an object
   with start_sec (float), end_sec (float), and hook_summary (a short
   Arabic phrase a human could put on the thumbnail, max 10 words).
8. Aim for {target} clips. If the video does not have {target} strong
   moments, return fewer rather than padding with weak ones.
9. Never invent timestamps outside the transcript's range.

Return ONLY the JSON object. No explanation, no markdown fence.
"""


def _build_prompt(cfg: SelectorConfig, feed: str) -> str:
    system = _SYSTEM.format(
        min_len=int(cfg.min_len_sec),
        max_len=int(cfg.max_len_sec),
        target=cfg.target_count,
    )
    return f"{system}\n\n---\nTranscript:\n{feed}\n"


# --------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------- #

def select_clips(
    *,
    transcript_json: Path,
    api_key: str,
    cfg: SelectorConfig,
) -> list[ClipPlan]:
    """Call Gemini; return a validated list of ClipPlan."""
    data = json.loads(Path(transcript_json).read_text(encoding="utf-8"))
    words: list[dict] = data["words"]
    duration = float(data.get("duration") or (words[-1]["end"] if words else 0))
    if duration <= 0:
        raise ValueError("Transcript has zero duration; nothing to select from.")

    chunks = _group_into_sentences(words)
    feed = _render_feed(chunks)
    prompt = _build_prompt(cfg, feed)

    logger.info(
        "Calling Gemini (%s) with %d sentence chunks (video %.0fs)",
        cfg.model, len(chunks), duration,
    )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=cfg.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
        ),
    )
    raw = (response.text or "").strip()
    if not raw:
        raise RuntimeError("Gemini returned an empty response")

    parsed = json.loads(raw)
    raw_clips = parsed.get("clips") if isinstance(parsed, dict) else parsed
    if not isinstance(raw_clips, list) or not raw_clips:
        raise RuntimeError(f"Gemini did not return a non-empty clip list: {parsed!r}")

    plans: list[ClipPlan] = []
    for i, c in enumerate(raw_clips):
        start = float(c["start_sec"])
        end = float(c["end_sec"])
        if end <= start:
            logger.warning("Skipping clip with non-positive duration: %r", c)
            continue
        if end > duration + 1:
            logger.warning("Clipping end %.2fs to duration %.2fs", end, duration)
            end = duration
        plans.append({
            "idx": i,
            "start_sec": round(start, 2),
            "end_sec": round(end, 2),
            "hook_summary": str(c.get("hook_summary") or "").strip(),
        })

    if not plans:
        raise RuntimeError("Gemini returned clips but none were usable after validation")

    plans.sort(key=lambda p: p["start_sec"])
    for i, p in enumerate(plans):
        p["idx"] = i
    logger.info("Selected %d clips (lengths %.0fs – %.0fs)",
                len(plans),
                min(p["end_sec"] - p["start_sec"] for p in plans),
                max(p["end_sec"] - p["start_sec"] for p in plans))
    return plans
