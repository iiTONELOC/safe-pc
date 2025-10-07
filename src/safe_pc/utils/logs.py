"""
Description: This module provides reusable utilities for logging.

Functions exported by this module:
- `setup_logging(level: int = DEBUG, log_file: str = "safe_pc") -> Logger`:
    Configures root logging once for the entire process and returns it.
"""

from pathlib import Path
from logging.handlers import RotatingFileHandler
from logging import INFO, Logger, Formatter, StreamHandler, DEBUG, getLogger

from safe_pc.utils.utils import IS_TESTING, IS_VERBOSE


BACKUP_LOG_COUNT = 5  # in days
_configured = False  # module-level flag to ensure logging is only configured once


def _project_log_dir() -> Path:
    """Get the project's log directory, creating it if necessary."""
    log_dir = Path(__file__).resolve().parents[3] / "logs"
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _project_log_file():
    """Get the project's log file path."""
    log_file = "safe_pc_tests" if IS_TESTING() else "safe_pc"
    log_dir = _project_log_dir()
    log_path = log_dir / f"{log_file}.log"
    return log_path


def setup_logging(level: int = INFO, log_file: str = "safe_pc") -> Logger:
    """
    Configure root logging once for the entire process.
    Returns the package logger for convenience.

    Args:
        level: The level to set, i.e. INFO, DEBUG, ERROR, etc.

    Returns:
        The configured root-level logger
    """

    global _configured
    if _configured:
        return getLogger(log_file)

    # determine if we need DEBUG level logging
    if level != DEBUG and IS_TESTING() or IS_VERBOSE():
        level = DEBUG

    log_path = _project_log_file()
    fmt = Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")

    # File handler with rotation (10 MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_path,
        mode="a" if not IS_TESTING() else "w",
        backupCount=BACKUP_LOG_COUNT,
    )
    file_handler.setFormatter(fmt)

    # Console handler
    stream_handler = StreamHandler()
    stream_handler.setFormatter(fmt)

    # config logger
    root = getLogger()
    root.handlers.clear()
    root.name = log_file
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    root.info(
        f" Logging initialized. Log file: ./{Path(log_path).relative_to(Path.cwd())} ".center(
            80, "*"
        )
    )

    _configured = True
    return getLogger(log_file)
