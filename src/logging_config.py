from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

_configured = False


def configure_logging(log_dir: Optional[str] = None, level: str = "INFO"):
    """Configure loguru sinks for rotating file logs and stderr output."""
    global _configured
    if _configured:
        return logger

    resolved_log_dir = Path(log_dir) if log_dir else Path("logs")
    resolved_log_dir.mkdir(parents=True, exist_ok=True)

    # Clear default sink to avoid duplicate logs when configuring.
    logger.remove()

    logger.add(
        resolved_log_dir / "file_{time}.log",
        rotation="1 day",
        retention="7 days",
        level=level,
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
    logger.add(
        sys.stderr,
        level=level,
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    _configured = True
    return logger


__all__ = ["configure_logging", "logger"]
