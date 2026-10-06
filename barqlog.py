"""Minimal file logger so Barq's background engine can be diagnosed."""
import logging
from logging.handlers import RotatingFileHandler

from config import DATA_DIR

_LOG_FILE = DATA_DIR / "barq.log"

_handlers = None


def get_logger(name: str = "barq") -> logging.Logger:
    global _handlers
    logger = logging.getLogger(name)
    if _handlers is None:
        fh = RotatingFileHandler(str(_LOG_FILE), maxBytes=5_000_000, backupCount=2, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        # also mirror to stderr when a console is attached
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        _handlers = (fh, sh)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.propagate = False
        for handler in _handlers:
            logger.addHandler(handler)
    return logger
