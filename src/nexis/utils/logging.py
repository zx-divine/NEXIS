import logging
from logging.handlers import RotatingFileHandler


def configure(directory):
    logger = logging.getLogger("nexis")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        directory / "nexis.log", maxBytes=200000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
