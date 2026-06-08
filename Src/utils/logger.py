"""
Logger module for PySTA.
Provides centralized logging configuration with timestamped log files.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Global logger instance
_logger = None
_log_file = None


def get_logger(name=None):
    """
    Get or create a logger instance.

    Args:
        name (str, optional): Module name for the logger. Defaults to None.

    Returns:
        logging.Logger: Configured logger instance
    """
    global _logger, _log_file

    if _logger is None:
        # Create logs directory if it doesn't exist
        logs_dir = Path("Logs")
        logs_dir.mkdir(exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _log_file = logs_dir / f"pysta_{timestamp}.log"

        # Configure root logger
        _logger = logging.getLogger("PySTA")
        _logger.setLevel(logging.DEBUG)

        # Remove any existing handlers
        _logger.handlers.clear()

        # File handler with rotation (10 MB per file, keep 5 backups)
        file_handler = RotatingFileHandler(
            _log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)

        # Add handlers
        _logger.addHandler(file_handler)
        _logger.addHandler(console_handler)

        _logger.info(f"Logger initialized. Log file: {_log_file}")

    if name:
        return _logger.getChild(name)
    return _logger


def get_log_file():
    """Get the current log file path."""
    global _log_file
    return _log_file