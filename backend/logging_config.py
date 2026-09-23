"""Central logging configuration."""

import logging
import sys
from backend.config.settings import settings


def setup_logging() -> logging.Logger:
    """Configure structured console logging."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger("news_credibility")
    logger.setLevel(level)
    return logger


logger = setup_logging()
