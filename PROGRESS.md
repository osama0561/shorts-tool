# Shorts Tool — Progress

Long Arabic YouTube video → 10–20 vertical 1080×1920 shorts with
burned-in Arabic captions and logo overlays. Gemini for reasoning;
local `faster-whisper` for Arabic ASR.

---

## Session log

### 2026-04-19 — Governance + audit

**What we did**

- Audited inherited state from the previous `/root/shorts-tool`
  session (full audit below).
- **Transcription decision:** keep local `faster-whisper` (large-v3,
  int8). Reason: Gemini 2.5 Pro drifts on word timestamps over long
  audio and charges per audio minute. Recorded in `CLAUDE.md` and in
  the `transcriber.py` header.
- Created project governance:
  - `CLAUDE.md` — persistent context: mission, stack, architecture
    principles, code style rules, DO NOT list, phased workflow.
  - `README.md` — one-page OSS overview.
  - `MCP_ROADMAP.md` — MCP servers in use and candidates for later.
  - `scripts/cleanup.sh` — deletes old artifacts
    (inputs 7d, working 1d, outputs 30d).
  - `test_data/` (empty, with `.gitkeep`).
  - `logs/` (empty, with `.gitkeep`).
  - Expanded `.gitignore` to cover `logs/*`.
  - Added `LOG_LEVEL` to `.env.example`.
- Initialised git and committed everything as
  `chore: project governance + existing work`.

**Exceptions / deferred work** (logged per ground rule 5)

- Real `.env` still contains a live Gemini API key on disk. `.env` is
  gitignored so it won't push to GitHub, but user may want to rotate.
- GitHub PAT was pasted into chat and saved to `.env` without
  rotation. User acknowledged the risk and chose to proceed;
  `GITHUB_TOKEN` placeholder added to `.env.example`. Strong
  recommendation to rotate after the project stabilises.
- Stale rows in `shorts.db` from the prior run (YouTube id
  `WubpUUMoaUo`) not deleted yet — `*.db` is gitignored, so harmless
  for the commit. Will be wiped before the Phase 1 smoke test.
- `.claude/settings.local.json` still allow-lists `/root/shorts-tool`
  paths — machine-local, not pushed; harmless, will be updated when
  next permission prompt surfaces.
- Code still uses `print()` (not `logging`), has no disk-space guard,
  no `storage.py` abstraction, and ffmpeg calls are not
  `nice`/`ionice`-prefixed. These are the first items in the Phase 1
  cleanup pass next session.

**User action still needed**

- Drop a 30-second Arabic sample video into `test_data/` before the
  Phase 1 smoke test runs.
- Provide MCP endpoint URL + auth token for n8n.
- Provide OAuth client credentials + target folder ID for the Google
  Drive MCP.
- Add the crontab line printed in chat so `scripts/cleanup.sh` runs
  daily at 3am.
- Decide whether to rotate the Gemini API key currently in `.env`.

---

## Phase map

| Phase | Scope                                   | Status |
|-------|-----------------------------------------|--------|
| 1     | Download + transcribe                   | Code complete, not yet run end-to-end at this path |
| 2     | Clip selection (Gemini picks hooks)     | Not started |
| 3     | Arabic captions (ASS burn-in)           | Not started |
| 4     | Logo overlays                           | Not started |
| 5     | Orchestration (stages, resume)          | Not started |

## What exists

- `main.py` — Phase 1 CLI: download → transcribe → record in DB.
- `shorts_tool/config.py` — `.env` loader, `Config` dataclass,
  `ensure_dirs()`.
- `shorts_tool/db.py` — schema for `videos`, `transcripts`, `clips`;
  helpers for videos + transcripts only (clip helpers not yet
  written).
- `shorts_tool/downloader.py` — `yt-dlp` wrapper with cookie support.
- `shorts_tool/transcriber.py` — local `faster-whisper` (large-v3,
  int8, CPU).
- Governance files: `CLAUDE.md`, `README.md`, `MCP_ROADMAP.md`,
  `PROGRESS.md`, `.env.example`, `.gitignore`.
- `scripts/cleanup.sh` — retention-based artifact cleanup.
- Empty runtime dirs: `inputs/`, `working/`, `outputs/`, `logos/`,
  `logs/`, `test_data/` (all with `.gitkeep`).
- `.venv/` with all dependencies installed.

## What works

- Phase 1 code compiles and imports resolve.
- DB schema initialises cleanly.
- Governance + repo layout in place.

## What's incomplete

- Phase 1 has never run end-to-end at this path — waiting on a
  `test_data/` sample before the smoke test.
- Engineering hygiene not yet applied to existing Phase 1 code
  (`print` → `logging`, disk-space guard, `nice`/`ionice` prefix,
  `storage.py` abstraction).
- Phases 2 / 3 / 4 / 5 not started.

## Next session — recommended order

1. Drop a 30-second Arabic sample into `test_data/`.
2. Phase 1 cleanup pass:
   - Introduce `logging` module, wire `LOG_LEVEL` + `logs/shorts.log`.
   - Add `shorts_tool/storage.py` with `save_file` / `load_file` /
     `delete_file`.
   - Add disk-space guard (<5 GB → abort).
   - Prefix every ffmpeg call with `nice -n 10 ionice -c 3`.
   - Wipe stale `shorts.db` rows and fix
     `.claude/settings.local.json` paths.
   - Commit (`refactor: Phase 1 engineering hygiene`).
3. Phase 1 smoke test end-to-end on the sample.
   Commit (`test: Phase 1 smoke test`).
4. Phase 2 scaffold:
   - `shorts_tool/clip_selector.py` — Gemini 2.5 Pro → list of
     `{start_sec, end_sec, hook_summary}`.
   - `shorts_tool/cutter.py` — ffmpeg cut + 1080×1920 reframe.
   - `db.py` clip helpers (`insert_clip`, `update_clip_paths`).
   - Extend `main.py` to let Phase 2 run against an existing
     `video_id`.

## Useful facts

- Project root: `/home/nahrai/shorts-tool`
- Python: `.venv/bin/python`
- Gemini models (from `.env`): reasoning `gemini-2.5-pro`, flash
  `gemini-2.5-flash`. Transcription slot exists but is unused
  (Whisper is in control).
- YouTube bot-check workaround: `COOKIES_FILE` or
  `COOKIES_FROM_BROWSER` in `.env`.
