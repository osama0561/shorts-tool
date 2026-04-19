"""Arabic transcription via local Whisper (faster-whisper / CTranslate2).

Why not Gemini for this step?
    Gemini 2.5 Pro returns unreliable word-level timestamps on long audio
    (it compresses time onto its video-token timeline) and charges per
    minute of audio regardless. Whisper is purpose-built for ASR, runs
    locally, is deterministic, and is free. Later pipeline stages
    (clip selection, emphasis detection, tool detection) still use Gemini
    for reasoning — that's where Gemini earns its keep.

Pipeline:
    1. Extract a mono 16 kHz MP3 from the source video (ffmpeg).
    2. Load a faster-whisper model (default large-v3 int8 on CPU).
    3. Transcribe with word_timestamps=True and language="ar".
    4. Write a {language, model, words: [{word, start, end}, ...]} JSON.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import TypedDict

from faster_whisper import WhisperModel


class WordTiming(TypedDict):
    word: str    # Arabic token as transcribed
    start: float # seconds from the start of the audio
    end: float   # seconds from the start of the audio


# Defaults picked for a CPU-only box: int8 quantisation + large-v3 is the
# sweet spot of Arabic quality vs. memory (~2 GB RAM) and speed (~2-3×
# realtime on modest CPUs). Override via env or function args if you have
# a GPU or want to trade accuracy for speed.
_DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "large-v3")
_DEFAULT_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
_DEFAULT_COMPUTE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")


def _extract_audio(video_path: Path, out_path: Path) -> Path:
    """Pull a small mono 16 kHz WAV out of the source video via ffmpeg."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",                 # drop video
            "-ac", "1",            # mono
            "-ar", "16000",        # 16 kHz — Whisper's native sample rate
            "-c:a", "pcm_s16le",   # uncompressed; skips MP3 encode/decode
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    return out_path


def transcribe(
    *,
    video_path: Path,
    working_dir: Path,
    language: str = "ar",
    model_name: str = _DEFAULT_MODEL,
    device: str = _DEFAULT_DEVICE,
    compute_type: str = _DEFAULT_COMPUTE,
    # These kwargs are accepted-but-ignored so callers written against the
    # old Gemini signature keep working.
    api_key: str | None = None,
) -> tuple[Path, dict]:
    """Transcribe a local video and return (json_path, transcript_dict).

    Returns a dict of shape:
        {
          "language":   "ar",
          "model":      "whisper-large-v3",
          "source":     "<input video filename>",
          "duration":   <float seconds>,
          "word_count": <int>,
          "words":      [{"word": str, "start": float, "end": float}, ...]
        }
    """
    del api_key  # accepted for API compatibility; Whisper is local

    working_dir.mkdir(parents=True, exist_ok=True)
    audio_path = working_dir / f"{video_path.stem}.wav"
    print(f"[transcribe] Extracting audio → {audio_path.name}")
    _extract_audio(video_path, audio_path)

    print(
        f"[transcribe] Loading Whisper model '{model_name}' "
        f"(device={device}, compute_type={compute_type})"
    )
    load_start = time.time()
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    print(f"[transcribe] Model loaded in {time.time() - load_start:.1f}s")

    print(f"[transcribe] Transcribing (language={language})…")
    transcribe_start = time.time()
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,
        # vad_filter skips long silences, which speeds things up without
        # hurting accuracy for talking-head-style content.
        vad_filter=True,
        # Mild beam search; higher is slower but marginally more accurate.
        beam_size=5,
    )

    words: list[dict] = []
    last_progress = 0.0
    for seg in segments:
        if seg.words is None:
            # Rare: whole segment without word-level timing. Treat the whole
            # segment as a single word-ish token.
            words.append({
                "word": seg.text.strip(),
                "start": round(float(seg.start), 2),
                "end": round(float(seg.end), 2),
            })
            continue
        for w in seg.words:
            words.append({
                "word": w.word.strip(),
                "start": round(float(w.start), 2),
                "end": round(float(w.end), 2),
            })
        # Log progress every ~30 s of audio decoded so the user sees activity.
        if seg.end - last_progress > 30:
            last_progress = seg.end
            print(f"[transcribe]   …{seg.end:6.1f}s decoded "
                  f"({len(words)} words so far)")

    elapsed = time.time() - transcribe_start
    print(f"[transcribe] Done in {elapsed:.1f}s "
          f"(audio duration {info.duration:.1f}s, "
          f"speed {info.duration / elapsed:.2f}× realtime)")

    transcript = {
        "language": language,
        "model": f"whisper-{model_name}",
        "source": video_path.name,
        "duration": round(float(info.duration), 2),
        "word_count": len(words),
        "words": words,
    }

    json_path = working_dir / f"{video_path.stem}.transcript.json"
    json_path.write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[transcribe] Saved {len(words)} words → {json_path}")
    return json_path, transcript
