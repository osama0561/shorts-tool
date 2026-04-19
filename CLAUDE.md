# CLAUDE.md — Project Context

Persistent context for every Claude Code session on this project. Read
this first, then respect it over general defaults.

## Mission

Turn one long-form Arabic YouTube video into **10–20 vertical 1080×1920
short-form videos**, each with:

- burned-in Arabic captions (word-accurate timing),
- a fixed logo overlay,
- a self-contained hook (usable standalone on TikTok / Reels / Shorts).

Target: feed in a 60-minute lecture, get ~15 publish-ready shorts out
in one unattended run.

## Stack

- **Language:** Python 3.12.
- **AI:**
  - `gemini-2.5-pro` — reasoning: clip selection, emphasis detection.
  - `gemini-2.5-flash` — cheap classification / simple labelling.
  - **Transcription is NOT Gemini.** Arabic word-level ASR runs locally
    on `faster-whisper` (large-v3, int8) because Gemini 2.5 Pro drifts
    on word timestamps over long audio and charges per audio minute.
    Revisit only if Arabic accuracy becomes a bottleneck.
- **Download:** `yt-dlp` (cookie support for YouTube bot-check).
- **Video ops:** `ffmpeg` via subprocess, always prefixed
  `nice -n 10 ionice -c 3` so the VPS stays responsive for other work.
- **State:** SQLite (single-file `shorts.db` at project root).
- **Delivery (planned):** Google Drive MCP.
- **Orchestration (planned):** n8n MCP.

## Architecture principles

1. **One module per pipeline stage.** `downloader`, `transcriber`,
   `clip_selector`, `cutter`, `captioner`, `brander`, `orchestrator`.
   Stages communicate through the DB + filesystem — never direct
   imports of another stage's internals.
2. **Filesystem is the source of truth for artifacts; SQLite is the
   index.** Re-running a stage against the same `video_id` must be
   idempotent.
3. **Fail loud, fail early.** Let unhandled exceptions bubble. No
   silent fallbacks that degrade quality.
4. **Storage is abstracted.** All file I/O goes through
   `shorts_tool/storage.py` (`save_file` / `load_file` / `delete_file`)
   so local disk can later be swapped for S3 / Drive without touching
   callers.
5. **Config comes from `.env`.** Never hardcode paths, model IDs, or
   thresholds. `shorts_tool/config.py` is the single reader of env vars.
6. **No global state.** Pass `Config` explicitly into every function
   that needs it.

## Code style rules (non-negotiable)

- Python type hints on every function signature.
- One-line docstring on every function. Keep it one line.
- **No `print()`.** Use the `logging` module; output goes to
  `./logs/shorts.log` (and stderr at the configured level).
- No hardcoded paths. Everything via `python-dotenv` through
  `config.py`.
- No API keys or secrets in any committed file. `.env` stays
  gitignored; `.env.example` ships placeholders.
- Every ffmpeg invocation prefixed with `nice -n 10 ionice -c 3`.
- Every pipeline run starts with a disk-space guard — abort if
  <5 GB free.
- Commit after each working phase with a Conventional-Commits
  message (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`).

## DO NOT

- DO NOT introduce a new AI provider without discussion. Gemini +
  local Whisper only.
- DO NOT add "fallback" logic that silently downgrades quality
  (e.g. "if Gemini errors, pick clips with a regex"). Fail the run.
- DO NOT commit `.env`, `*.db`, or anything under `inputs/`,
  `working/`, `outputs/`, `logs/`.
- DO NOT write new abstractions until a concrete second caller exists.
- DO NOT add features that weren't in the phase plan for this session.
- DO NOT bypass `nice` / `ionice` on ffmpeg. The VPS is shared.
- DO NOT write more than ~200 lines of code without running something.
- DO NOT skip `PROGRESS.md` updates or git commits between phases.

## How we work

The build is phased. Move linearly. Do not jump ahead.

| Phase | Scope                                               |
|-------|-----------------------------------------------------|
| 1     | Foundation: download + transcribe → DB + filesystem |
| 2     | Clip selection: Gemini picks hooks; ffmpeg cuts     |
| 3     | Captions: word-aligned ASS, burned in               |
| 4     | Logo overlays                                       |
| 5     | Orchestration: single-command end-to-end run        |

**Working loop inside a phase:**

1. Smallest testable slice first. Run it on real sample data from
   `test_data/`.
2. When the slice is green, update `PROGRESS.md`.
3. Commit with a conventional message.
4. Repeat until the phase is done.
5. At the phase boundary: update `PROGRESS.md`, note the commit, then
   move on.

**Order of priorities (do not invert):**

1. Working ugly version, end-to-end.
2. Iterate on quality with real Arabic content.
3. Polish for open-source release.

If the user says "just ship it" / "skip planning" / "polish first
before it works" — push back once and remind them of this order.

**Session close rule:** Update `PROGRESS.md` at the END of every
session with current state and next steps. This is non-negotiable —
tmux sessions can die, `PROGRESS.md` is the durable record.

## Session kickoff checklist

At the start of every session, Claude Code should:

1. Read `CLAUDE.md`, `PROGRESS.md`, and the `shorts_tool/` package.
2. Confirm the current phase from `PROGRESS.md`.
3. State, before writing code, what it plans to do this session.
4. Honour the DO NOT list above.
