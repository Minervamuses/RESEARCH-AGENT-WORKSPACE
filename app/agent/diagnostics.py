"""Local, redacted diagnostic log for the chat CLI and the desktop backend.

Entry points call :func:`install_diagnostic_log` once. Records go to one
rotating, owner-only file per component under ``$AGENT_LOG_DIR`` or
``$XDG_STATE_HOME/research-agent/logs`` (default
``~/.local/state/research-agent/logs``):

* ``agent``, ``skills``, and ``rag`` loggers at INFO and above;
* third-party libraries at WARNING and above (httpx request lines, which
  can carry query-string credentials, stay below the threshold).

Before a record is written, values of credential-named environment
variables and credential-shaped text (``api_key=…``, ``Bearer …``,
``mailto:…``) are replaced with ``[redacted]``. Application loggers never
log message content (see :mod:`agent.observability`); tracebacks carry
exception text only. :func:`new_incident_id` gives user-facing errors a
short reference that also appears in the matching log record.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
import sys
import uuid
from collections.abc import Iterable, Mapping
from pathlib import Path

from agent.paths import user_state_root

LOG_DIR_ENV = "AGENT_LOG_DIR"
MAX_LOG_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3
APP_LOGGERS = ("agent", "skills", "rag")
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [pid %(process)d] %(message)s"

_SECRET_NAME_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD")
_MIN_SECRET_LENGTH = 8
_SECRET_PATTERNS = (
    re.compile(
        r"(?i)\b((?:api[_-]?key|access[_-]?token|token|secret|password|key)=)"
        r"[^&\s\"']+"
    ),
    re.compile(r"(?i)\b(bearer\s+)[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(mailto[:=])[^\s&\"')]+"),
)

_installed: tuple[Path | None, list[logging.Handler]] | None = None


def diagnostic_log_dir(env: Mapping[str, str] | None = None) -> Path:
    """Return the configured diagnostic log directory."""
    env = dict(os.environ) if env is None else dict(env)
    raw = env.get(LOG_DIR_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    return user_state_root(env) / "research-agent" / "logs"


def new_incident_id() -> str:
    """Return a short reference shared by a user-facing error and its log record."""
    return uuid.uuid4().hex[:8]


def current_log_path() -> Path | None:
    """Return the active diagnostic log file, or None when none is installed."""
    return _installed[0] if _installed is not None else None


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    """Blank out known secret values and credential-shaped substrings."""
    for secret in secrets:
        text = text.replace(secret, "[redacted]")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[redacted]", text)
    return text


def _env_secrets(env: Mapping[str, str]) -> tuple[str, ...]:
    values = {
        value.strip()
        for name, value in env.items()
        if any(marker in name.upper() for marker in _SECRET_NAME_MARKERS)
        and len(value.strip()) >= _MIN_SECRET_LENGTH
    }
    # Longest first so a secret containing another is blanked whole.
    return tuple(sorted(values, key=len, reverse=True))


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts the fully formatted record, traceback included."""

    def __init__(self, fmt: str | None = None, *, secrets: Iterable[str] = ()):
        super().__init__(fmt)
        self._secrets = tuple(secrets)

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record), self._secrets)


class _PrivateRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating handler whose current and rolled-over files are mode 0600."""

    def _open(self):
        fd = os.open(
            self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
        )
        return open(fd, self.mode, encoding=self.encoding, errors=self.errors)


def install_diagnostic_log(
    component: str,
    *,
    echo_stderr: bool,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    """Attach the diagnostic log handlers to the root logger (idempotent).

    ``echo_stderr`` keeps WARNING+ records on stderr in plain form, as the
    CLI showed them before. When the log file cannot be created, records
    fall back to stderr and None is returned.
    """
    global _installed
    if _installed is not None:
        return _installed[0]
    env = dict(os.environ) if env is None else dict(env)
    secrets = _env_secrets(env)
    handlers: list[logging.Handler] = []
    path: Path | None = None
    failure: OSError | None = None
    try:
        directory = diagnostic_log_dir(env)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / f"{component}.log"
        file_handler = _PrivateRotatingFileHandler(
            path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError as exc:
        path = None
        failure = exc
    else:
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(RedactingFormatter(LOG_FORMAT, secrets=secrets))
        handlers.append(file_handler)
    if echo_stderr or path is None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setLevel(logging.WARNING)
        stream_handler.setFormatter(RedactingFormatter("%(message)s", secrets=secrets))
        handlers.append(stream_handler)

    root = logging.getLogger()
    for handler in handlers:
        root.addHandler(handler)
    for name in APP_LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)
    _installed = (path, handlers)

    logger = logging.getLogger(__name__)
    if path is None:
        logger.warning("diagnostic log file unavailable: %s", failure)
    else:
        logger.info("diagnostic log started for %s", component)
    return path


def uninstall_diagnostic_log() -> None:
    """Detach and close the installed handlers (used by tests)."""
    global _installed
    if _installed is None:
        return
    root = logging.getLogger()
    for handler in _installed[1]:
        root.removeHandler(handler)
        handler.close()
    for name in APP_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)
    _installed = None
