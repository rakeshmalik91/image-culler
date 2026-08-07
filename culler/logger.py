import logging
from pathlib import Path

# Setup culler_debug.log file logger
log_file = Path(__file__).resolve().parent.parent / "culler_debug.log"

logger = logging.getLogger("culler")
logger.setLevel(logging.DEBUG)

# File Handler
fh = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
fh.setFormatter(formatter)

# Console Handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(fh)
    logger.addHandler(ch)


def log_debug(msg: str):
    logger.debug(msg)


def log_info(msg: str):
    logger.info(msg)


def log_error(msg: str, exc_info: bool = False):
    logger.error(msg, exc_info=exc_info)
