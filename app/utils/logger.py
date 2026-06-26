import logging
import sys


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Create a configured logger with consistent formatting."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(level)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Pre-configured loggers for each subsystem
parser_logger = setup_logger("validator.parser")
db_logger = setup_logger("validator.db")
rag_logger = setup_logger("validator.rag")
pipeline_logger = setup_logger("validator.pipeline")
