"""Jarvis Logging Configuration."""

import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(level: str = "INFO") -> None:
    """Configure Jarvis logging with console + file output."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt=date_fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_DIR / "jarvis.log", encoding="utf-8"),
        ],
    )

    noisy = ["urllib3", "httpx", "httpcore", "chromadb", "onnxruntime"]
    for name in noisy:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger("Jarvis").info("Logging initialized at %s level", level)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance."""
    return logging.getLogger(f"Jarvis.{name}")
