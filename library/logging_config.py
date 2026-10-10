"""Logging setup: every key action is written to ``logs/library.log``.

Modules obtain loggers with ``logging.getLogger(__name__)``; because they all
live under the ``library`` package, a single file handler attached to the
``library`` logger captures everything.
"""

from __future__ import annotations

import logging
from pathlib import Path

LOG_FILE = Path("logs") / "library.log"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(log_file: Path | str = LOG_FILE, level: int = logging.INFO) -> None:
    """Attach a file handler to the ``library`` logger.

    Safe to call more than once: a second call for the same file does not add
    a duplicate handler (which would write every line twice).
    """
    log_path = Path(log_file).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    package_logger = logging.getLogger("library")
    package_logger.setLevel(level)
    for handler in package_logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path:
            return

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    package_logger.addHandler(file_handler)
