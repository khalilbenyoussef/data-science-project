"""Logging console + fichier, sans handlers dupliques."""

from __future__ import annotations

import logging
from pathlib import Path

from biflow.config import ROOT

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str = "biflow", log_file: str | Path | None = None) -> logging.Logger:
    """Retourne un logger console + fichier (outputs/logs/biflow.log par defaut)."""
    logger = logging.getLogger(name)
    if getattr(logger, "_biflow_configured", False):
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
    logger.addHandler(console)

    target = Path(log_file) if log_file else ROOT / "outputs" / "logs" / "biflow.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(target, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
    logger.addHandler(file_handler)

    logger._biflow_configured = True  # type: ignore[attr-defined]
    return logger
