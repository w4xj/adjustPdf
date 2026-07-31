"""日志配置。"""

import logging
import os
from pathlib import Path

LOGGER_NAME = "adjust_pdf"


def get_log_directory() -> Path:
    """返回适合当前系统的日志目录。"""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return base / "AdjustPdf" / "logs"


def configure_logging() -> Path:
    """初始化文件日志，并返回日志文件路径。"""
    log_directory = get_log_directory()
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "adjust-pdf.log"

    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)

    return log_path


def get_logger(name: str | None = None) -> logging.Logger:
    suffix = f".{name}" if name else ""
    return logging.getLogger(f"{LOGGER_NAME}{suffix}")
