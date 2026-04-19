"""Phase 4 — word-timed Arabic captions burned into a reframed clip.

Takes a word-level transcript (global times) and a clip window
[start_sec, end_sec], and produces an ASS subtitle file whose events
are expressed in clip-local time. Then runs ffmpeg with the libass
filter to burn the captions into the already-reframed 1080×1920 mp4.

Visual: ~3 Arabic words per line; each word lights up in yellow while
spoken, the rest stay white. Bottom-center, thick black outline.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from shorts_tool.storage import save_text


logger = logging.getLogger("shorts.captioner")

_FFMPEG_NICE = ["nice", "-n", "10", "ionice", "-c", "3"]

# Font path must be absolute for libass in an ffmpeg context.
_FONT_PATH = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
_FONT_NAME = "Noto Naskh Arabic"

_WORDS_PER_LINE = 3
_SENTENCE_BREAK = re.compile(r"[\.؟\?!،,…]+\s*$")


class Word(TypedDict):
    word: str
    start: float
    end: float


@dataclass(frozen=True)
class CaptionStyle:
    font: str = _FONT_NAME
    font_size: int = 72
    primary_bgr: str = "&H00FFFFFF"   # white (BBGGRR with AA=00 opaque)
    highlight_bgr: str = "&H0000E5FF"  # warm yellow
    outline_bgr: str = "&H00000000"    # black
    outline_px: int = 5
    shadow_px: int = 2
    margin_v: int = 240                # px up from bottom


# --------------------------------------------------------------------- #
# Transcript slicing + line grouping
# --------------------------------------------------------------------- #

def _clip_local_words(
    words: list[Word], start_sec: float, end_sec: float
) -> list[Word]:
    """Return words inside [start,end] with times rebased to clip-local."""
    out: list[Word] = []
    for w in words:
        if w["end"] < start_sec or w["start"] > end_sec:
            continue
        out.append({
            "word": w["word"],
            "start": max(0.0, w["start"] - start_sec),
            "end": max(0.0, min(w["end"], end_sec) - start_sec),
        })
    return out


def _group_lines(words: list[Word], per_line: int = _WORDS_PER_LINE) -> list[list[Word]]:
    """Group words into lines; break early on sentence-ending punctuation."""
    lines: list[list[Word]] = []
    buf: list[Word] = []
    for w in words:
        buf.append(w)
        if len(buf) >= per_line or _SENTENCE_BREAK.search(w["word"]):
            lines.append(buf); buf = []
    if buf:
        lines.append(buf)
    return lines


# --------------------------------------------------------------------- #
# ASS assembly
# --------------------------------------------------------------------- #

def _fmt_ass_time(t: float) -> str:
    """Convert seconds to ASS ``H:MM:SS.cs`` format (centiseconds)."""
    if t < 0:
        t = 0.0
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_header(style: CaptionStyle) -> str:
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n"
        "WrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{style.font},{style.font_size},"
        f"{style.primary_bgr},{style.highlight_bgr},"
        f"{style.outline_bgr},&H80000000,"
        "1,0,0,0,100,100,0,0,"
        f"1,{style.outline_px},{style.shadow_px},"
        f"2,40,40,{style.margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )


def _highlight_line(
    words: list[Word], active_idx: int, style: CaptionStyle
) -> str:
    """Return the ASS Text field for a line with one word highlighted."""
    parts: list[str] = []
    for i, w in enumerate(words):
        token = w["word"]
        if i == active_idx:
            parts.append(f"{{\\c{style.highlight_bgr}}}{token}{{\\r}}")
        else:
            parts.append(token)
    return " ".join(parts)


def build_ass(
    *,
    words: list[Word],
    clip_start_sec: float,
    clip_end_sec: float,
    style: CaptionStyle = CaptionStyle(),
) -> str:
    """Render an .ass document for a clip window."""
    local = _clip_local_words(words, clip_start_sec, clip_end_sec)
    lines = _group_lines(local)
    events: list[str] = []

    for line in lines:
        if not line:
            continue
        line_end = line[-1]["end"]
        for i, w in enumerate(line):
            event_start = w["start"]
            event_end = line[i + 1]["start"] if i + 1 < len(line) else line_end
            if event_end <= event_start:
                event_end = event_start + 0.05
            text = _highlight_line(line, i, style)
            events.append(
                f"Dialogue: 0,{_fmt_ass_time(event_start)},"
                f"{_fmt_ass_time(event_end)},Default,,0,0,0,,{text}"
            )

    return _ass_header(style) + "\n".join(events) + "\n"


# --------------------------------------------------------------------- #
# Burn-in
# --------------------------------------------------------------------- #

def burn_captions(
    *,
    clip_video: Path,
    words: list[Word],
    clip_start_sec: float,
    clip_end_sec: float,
    out_path: Path,
    style: CaptionStyle = CaptionStyle(),
) -> Path:
    """Burn word-timed Arabic captions onto ``clip_video``."""
    ass_text = build_ass(
        words=words,
        clip_start_sec=clip_start_sec,
        clip_end_sec=clip_end_sec,
        style=style,
    )
    ass_path = out_path.with_suffix(".ass")
    save_text(ass_path, ass_text)

    # libass needs a font config that finds the family. Point it at the
    # directory containing the bold TTF so lookups succeed even without
    # a full fontconfig refresh.
    fonts_dir = str(Path(_FONT_PATH).parent)
    ass_arg = f"ass={ass_path}:fontsdir={fonts_dir}"

    cmd = [
        *_FFMPEG_NICE,
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(clip_video),
        "-vf", ass_arg,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(out_path),
    ]
    logger.info("Burning captions → %s", out_path.name)
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path
