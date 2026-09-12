"""Privacy-safe rotating diagnostics for the packaged local service."""

from __future__ import annotations

import logging
import platform
import re
import sys
import traceback
from importlib import metadata
from logging.handlers import RotatingFileHandler
from pathlib import Path

from nexora.version import APP_VERSION

LOGGER_NAME = "nexora"
_SECRET = re.compile(
    r"(?i)(gemini_api_key|api[_ -]?key|authorization|token|password)\s*[:=]\s*\S+"
)
_KEY = re.compile(r"\b(?:sk|AIza)[A-Za-z0-9_-]{12,}\b")


def sanitize(value: object) -> str:
    """Remove credential-shaped data and avoid recording private request content."""
    text = str(value or "")
    text = _SECRET.sub(r"\1=[redacted]", text)
    return _KEY.sub("[redacted]", text)


def configure(data_dir: Path, build_profile: str) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "nexora-backend.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)sZ %(levelname)s %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    logger.info(
        "version=%s profile=%s stage=startup windows=%s python=%s frozen=%s",
        APP_VERSION,
        build_profile,
        platform.platform(),
        platform.python_version(),
        bool(getattr(sys, "frozen", False)),
    )
    versions = []
    for package in ("fastapi", "uvicorn", "pydantic", "sqlalchemy", "httpx", "flet"):
        try:
            versions.append(f"{package}={metadata.version(package)}")
        except metadata.PackageNotFoundError:
            versions.append(f"{package}=missing")
    logger.info("stage=dependency-check %s", " ".join(versions))
    return logger


def safe_traceback(exc: BaseException) -> str:
    """Return stack locations without exception values or local variables."""
    frames = traceback.extract_tb(exc.__traceback__)
    home = str(Path.home())
    return " | ".join(
        f"{frame.filename.replace(home, '%USERPROFILE%')}:{frame.lineno}:{frame.name}"
        for frame in frames[-12:]
    )


def safe_exception_category(exc: BaseException) -> str:
    """Return only an exception class; messages can contain user or provider data."""
    return type(exc).__name__
