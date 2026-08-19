"""Minimal file logger so Barq's background engine can be diagnosed."""
import logging

from config import DATA_DIR

_LOG_FILE = DATA_DIR / "barq.log"

_configured = False


def get_logger(name: str = "barq") -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)
    if not _configured:
        _configured = True
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(str(_LOG_FILE), encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        logger.addHandler(fh)
        # also mirror to stderr when a console is attached
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(sh)
    return logger