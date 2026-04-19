# Shorts Tool — Progress

Long Arabic YouTube video → 10–20 vertical 1080×1920 shorts with
burned-in Arabic captions and logo overlays. Gemini for reasoning;
local `faster-whisper` for Arabic ASR.

---

## Session log

### 2026-04-19 (evening) — GitHub + YouTube auth + input pipeline

**What we did**

- Published repo to GitHub: `osama0561/shorts-tool` (public). Had to
  expand the fine-grained PAT's repo-selection to "All repositories"
  and grant `Contents: Read and write` before `git push` worked.
  Cleaned the token out of `.git/config` (remote URL is tokenless;
  pushes use the inline `https://oauth2:$TOKEN@...` form).
- **YouTube download dead end on this VPS.** The VPS IP is bot-flagged
  by YouTube. Tried three bypasses:
  1. `yt-dlp-youtube-oauth2` plugin — **broken.** Google's device-code
     endpoint now returns HTTP 400 before the plugin can poll. Do not
     waste time on it again. Uninstalled.
  2. BgUtils PO token provider (`bgutil-ytdlp-pot-provider`) — **works
     on big popular videos** (verified against a Rickroll). **Does not
     bypass the bot-flag on smaller channels** like the user's — all
     player clients still return `LOGIN_REQUIRED` even with a valid
     PO token. Kept installed anyway; useful for public mainstream
     videos and costs us nothing.
  3. Confirmed via incognito-browser test on the user's own public
     video (`WubpUUMoaUo`) that the block is purely IP-flag, not
     a video-level restriction.
- **Input decision: skip YouTube download entirely.** Files come in
  via Google Drive → `gdown` → `inputs/youtube/`. The user drops the
  source video in a Drive folder; we pull it. This is also what
  commercial tools like Opus Clip actually do (upload-your-own-file).
  No cookies, no proxies, no maintenance. Full quality (user's
  original upload, not YouTube's re-encode).
- Downloaded the first real test video:
  `inputs/youtube/linkedin_no_silence.mp4` — 1920×1080, H264, 19m 28s,
  318 MB. Cut a 30-sec sample to `test_data/sample_linkedin_30s.mp4`
  for the Phase 1 smoke test.
- Created `scripts/setup_pot_provider.sh` to reproduce the BgUtils
  setup in `vendor/` from scratch (clones at the plugin version
  installed in the venv, `npm ci`, `npx tsc`). Gitignored `vendor/`
  so we never commit 300+ npm packages.
- Gitignored `test_data/*` (personal video content stays out of the
  public repo); `.gitkeep` retained.

**Decisions recorded**

- **No residential proxy yet.** Not worth the $5–15/mo until we have
  a use case beyond the user's own videos. Drive upload is the
  primary input path.
- **No cookies yet.** If we ever need to scrape non-creator-owned
  YouTube content, we'll add a burner-account cookie jar at that
  point, not pre-emptively.
- **yt-dlp stays in the codebase** (`shorts_tool/downloader.py`) for
  public-video edge cases, but is no longer the blessed input path
  for the user's own content.

**Exceptions / deferred work**

- `shorts_tool/downloader.py` still assumes YouTube URLs. Needs a new
  entry point that accepts a local file path (e.g. from `gdown`).
  First item of the Phase 1 hygiene pass.
- Still need to wipe stale `shorts.db` rows from the prior run
  (video_id `WubpUUMoaUo`).
- Still need to fix `/root/shorts-tool` paths in
  `.claude/settings.local.json`.

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
| 1     | Ingest + transcribe                     | ✅ Smoke test passed 2026-04-19 on `test_data/sample_linkedin_30s.mp4` — 75 Arabic words with word-level timing, 0.35x realtime on CPU |
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

1. ~~Drop a 30-second Arabic sample into `test_data/`.~~ Done.
2. ~~Phase 1 cleanup pass.~~ Done (commit `28f364b`).
3. ~~Phase 1 smoke test end-to-end on the sample.~~ ✅ Passed
   (75 Arabic words transcribed from 30-sec clip, word-level timing,
   0.35x realtime on CPU).
4. **Speed caveat for Phase 1** — 0.35x realtime means a 60-min lecture
   takes ~3 hours of CPU to transcribe. Options to revisit:
   - Drop to `large-v3-turbo` or `medium` model (faster, Arabic still
     decent)
   - Run on GPU occasionally (rent a Paperspace / RunPod box)
   - Parallelise across audio chunks (whisper.cpp or faster-whisper
     with `num_workers`)
   Pick one only when the full-lecture wait becomes annoying.
5. Phase 2 scaffold:
   - `shorts_tool/clip_selector.py` — Gemini 2.5 Pro → list of
     `{start_sec, end_sec, hook_summary}`.
   - `shorts_tool/cutter.py` — ffmpeg cut + 1080×1920 reframe.
   - `db.py` clip helpers (`insert_clip`, `update_clip_paths`).
   - Extend `main.py` to let Phase 2 run against an existing
     `video_id`.

## Revisit later

- **Hyperframes** (`https://github.com/heygen-com/hyperframes`) — HTML
  → MP4 renderer. If the ASS subtitle burn-in in Phase 3 produces poor
  Arabic output (kashida spacing, word-level highlighting, diacritics),
  rewrite stages 5 (captions) and 6 (logo overlay) on top of
  Hyperframes. Decision: do not adopt before Phase 3 has run end-to-end
  on real Arabic content.

## Useful facts

- Project root: `/home/nahrai/shorts-tool`
- Python: `.venv/bin/python`
- Gemini models (from `.env`): reasoning `gemini-2.5-pro`, flash
  `gemini-2.5-flash`. Transcription slot exists but is unused
  (Whisper is in control).
- YouTube bot-check workaround: `COOKIES_FILE` or
  `COOKIES_FROM_BROWSER` in `.env`.
