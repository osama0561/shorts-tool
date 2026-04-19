"""Project-wide logging setup.

Called once from the CLI entrypoint. Logs go to both stderr and
``logs/shorts.log``. The level is taken from the ``LOG_LEVEL`` env var
(default ``INFO``); levels follow the standard library names.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def configure_logging(log_dir: Path) -> logging.Logger:
    """Configure the root logger; return the app logger. Idempotent."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if getattr(root, "_shorts_configured", False):
        return logging.getLogger("shorts")

    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    stderr = logging.StreamHandler()
    stderr.setFormatter(formatter)
    root.addHandler(stderr)

    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "shorts.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root._shorts_configured = True  # type: ignore[attr-defined]
    return logging.getLogger("shorts")
