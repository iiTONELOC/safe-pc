"""
Author: Anthony Tropeano
CYBV498: Senior Capstone in Cyber Operations
Date: 2025-09-13
Description: Logging utilities for the capstone package.
"""

from pathlib import Path
from logging import Logger, Formatter, StreamHandler, FileHandler, DEBUG, getLogger
from capstone.utils import IS_TESTING

_configured = False


def _project_log_dir() -> Path:
    """Get the project's log directory, creating it if necessary."""
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _project_log_file():

    log_file = "capstone_tests" if IS_TESTING() else "capstone"
    log_dir = _project_log_dir()
    log_path = log_dir / f"{log_file}.log"
    return log_path


def setup_logging(level: int = DEBUG, log_file: str = "capstone") -> Logger:
    """
    Configure root logging once for the entire process.
    Returns the package logger for convenience.

    Args:
        level: Root log level.

    Returns:
        A configured root-level logger
    """

    global _configured
    if _configured:
        return getLogger(log_file)

    log_path = _project_log_file()
    fmt = Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")

    # File handler (append mode, no rotation)
    file_handler = FileHandler(log_path, mode="a" if not IS_TESTING() else "w")
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
            60, "*"
        )
    )

    _configured = True
    return getLogger(log_file)
