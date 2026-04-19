# shorts-tool

Turn one long Arabic YouTube video into 10–20 vertical short-form
videos (1080×1920) with burned-in Arabic captions and a logo overlay.

## What it does

Given a YouTube URL, the tool:

1. Downloads the video with `yt-dlp`.
2. Transcribes the Arabic audio locally with `faster-whisper`
   (word-level timestamps).
3. Picks 10–20 self-contained hooks using Google Gemini 2.5 Pro.
4. Cuts each hook and reframes to 1080×1920 vertical with `ffmpeg`.
5. Burns word-accurate Arabic captions (ASS subtitle format).
6. Applies a fixed logo overlay.
7. Writes the finished shorts to `outputs/`.

One command per long video. ~15 publish-ready shorts per unattended
run.

## Requirements

- Python 3.12+
- `ffmpeg` on `PATH`
- A Google Gemini API key — <https://aistudio.google.com/apikey>
- ~5 GB free disk per run
- YouTube cookies if your IP is rate-limited (optional — see
  `.env.example`)

## Install

```bash
git clone <repo-url> shorts-tool
cd shorts-tool
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env — at minimum, set GEMINI_API_KEY
```

## Run

```bash
python main.py "https://www.youtube.com/watch?v=…"
```

Finished shorts land in `outputs/`. Intermediate artifacts (audio,
raw cuts, transcripts) live in `working/`. Logs go to `logs/`.

## Status

Early-stage. Phase 1 (download + transcribe) is implemented; Phases
2–5 (clip selection → captions → logos → orchestration) are in
progress. See `PROGRESS.md` for the current session's state and
`CLAUDE.md` for the architecture and working agreements.

## License

TBD.
