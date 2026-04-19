"""YouTube downloader wrapper around yt-dlp.

We shell out to the `yt-dlp` Python module rather than the CLI binary so the
download lives in-process and we can read metadata directly. The file is
saved to the configured inputs directory as `<youtube_id>.<ext>`.

YouTube increasingly blocks datacenter IPs with "Sign in to confirm you're
not a bot." If that happens, callers should supply cookies — either a
Netscape-format `cookies.txt` file or a browser profile name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yt_dlp


@dataclass(frozen=True)
class DownloadResult:
    youtube_id: str
    title: str
    duration_sec: float
    path: Path


def download(
    youtube_url: str,
    inputs_dir: Path,
    *,
    cookies_file: Path | None = None,
    cookies_from_browser: str | None = None,
) -> DownloadResult:
    """Download the best mp4 (video+audio) to `inputs_dir` and return metadata.

    yt-dlp picks the best pre-merged mp4 when available, falling back to
    merging the best video and audio streams through ffmpeg.

    If `cookies_file` or `cookies_from_browser` is supplied, yt-dlp uses
    those credentials — required when the server IP has been flagged by
    YouTube's bot check.
    """
    inputs_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts: dict = {
        # %(id)s keeps the filename stable across retries of the same URL.
        "outtmpl": str(inputs_dir / "%(id)s.%(ext)s"),
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    if cookies_file is not None:
        if not cookies_file.exists():
            raise FileNotFoundError(
                f"COOKIES_FILE points to {cookies_file}, which does not exist"
            )
        ydl_opts["cookiefile"] = str(cookies_file)

    if cookies_from_browser:
        # yt-dlp accepts a tuple like ("chrome",) or ("chrome", "Default")
        parts = tuple(s.strip() for s in cookies_from_browser.split(":") if s.strip())
        ydl_opts["cookiesfrombrowser"] = parts

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        # yt-dlp returns the actual on-disk path under `requested_downloads`
        # when available; fall back to rebuilding from template.
        downloaded_path: Path
        if info.get("requested_downloads"):
            downloaded_path = Path(info["requested_downloads"][0]["filepath"])
        else:
            downloaded_path = inputs_dir / f"{info['id']}.{info.get('ext', 'mp4')}"

    return DownloadResult(
        youtube_id=info["id"],
        title=info.get("title") or info["id"],
        duration_sec=float(info.get("duration") or 0.0),
        path=downloaded_path,
    )
