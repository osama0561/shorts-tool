"""Configuration loader.

Reads values from `.env` (via python-dotenv) and exposes them as a single
`Config` object. Every filesystem path is resolved relative to the project
root, so nothing in the codebase should hardcode absolute paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Project root = directory that contains this package's parent.
# `shorts_tool/config.py` → parents[1] is the repo root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Config:
    gemini_api_key: str
    reasoning_model: str
    flash_model: str
    transcription_model: str

    inputs_dir: Path
    working_dir: Path
    outputs_dir: Path
    logos_dir: Path

    db_path: Path

    # Optional YouTube auth. At most one of these is typically set.
    cookies_file: Path | None
    cookies_from_browser: str | None

    def ensure_dirs(self) -> None:
        """Create any missing runtime directories. Idempotent."""
        for d in (self.inputs_dir, self.working_dir, self.outputs_dir, self.logos_dir):
            d.mkdir(parents=True, exist_ok=True)


def _resolve(path_str: str) -> Path:
    """Expand and resolve a path; treat relative paths as relative to PROJECT_ROOT."""
    p = Path(os.path.expanduser(path_str))
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def load_config() -> Config:
    """Load `.env` and build a Config. Missing API key raises RuntimeError."""
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    cookies_file_raw = os.getenv("COOKIES_FILE", "").strip()
    cookies_from_browser = os.getenv("COOKIES_FROM_BROWSER", "").strip() or None

    return Config(
        gemini_api_key=api_key,
        reasoning_model=os.getenv("GEMINI_REASONING_MODEL", "gemini-2.5-pro"),
        flash_model=os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash"),
        transcription_model=os.getenv("GEMINI_TRANSCRIPTION_MODEL", "gemini-2.5-pro"),
        inputs_dir=_resolve(os.getenv("INPUTS_DIR", "inputs")),
        working_dir=_resolve(os.getenv("WORKING_DIR", "working")),
        outputs_dir=_resolve(os.getenv("OUTPUTS_DIR", "outputs")),
        logos_dir=_resolve(os.getenv("LOGOS_DIR", "logos")),
        db_path=_resolve(os.getenv("DB_PATH", "shorts.db")),
        cookies_file=_resolve(cookies_file_raw) if cookies_file_raw else None,
        cookies_from_browser=cookies_from_browser,
    )
