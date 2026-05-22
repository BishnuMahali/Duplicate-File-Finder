# core.Logging_Config.py — Production logging setup
"""Centralized logging configuration for CLI and library use."""

from __future__ import annotations

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Configure root logger with console and optional file handlers."""
    logger = logging.getLogger("dff_lite")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
