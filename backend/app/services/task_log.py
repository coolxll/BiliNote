import json
import logging
import os
import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


_current_task_id: ContextVar[Optional[str]] = ContextVar("current_task_id", default=None)
_write_lock = threading.Lock()
_handler: Optional[logging.Handler] = None
_TASK_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}")
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|cookie)"
    r"(\s*[=:]\s*)([^\s,;]+)"
)


def _log_dir() -> Path:
    return Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))


def _log_path(task_id: str) -> Path:
    if not _TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("invalid task id")
    return _log_dir() / f"{task_id}.logs.jsonl"


def _sanitize(message: str) -> str:
    sanitized = _SECRET_PATTERN.sub(r"\1\2***", message)
    return sanitized[:2000]


def append_task_log(
    task_id: str,
    message: str,
    level: str = "info",
    logger_name: str = "app.task",
) -> None:
    try:
        path = _log_path(task_id)
    except ValueError:
        return

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.lower(),
        "logger": logger_name,
        "message": _sanitize(message),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def reset_task_logs(task_id: str) -> None:
    try:
        path = _log_path(task_id)
    except ValueError:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        path.write_text("", encoding="utf-8")


def read_task_logs(task_id: str, limit: int = 120) -> list[dict]:
    try:
        path = _log_path(task_id)
    except ValueError:
        return []
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    entries = []
    for line in lines[-max(1, limit):]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return entries


@contextmanager
def task_log_context(task_id: str) -> Iterator[None]:
    install_task_log_handler()
    token = _current_task_id.set(task_id)
    try:
        yield
    finally:
        _current_task_id.reset(token)


class TaskLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        task_id = _current_task_id.get()
        if not task_id or not record.name.startswith("app."):
            return
        marker = "_bilinote_task_log_id"
        if getattr(record, marker, None) == task_id:
            return
        setattr(record, marker, task_id)
        try:
            append_task_log(
                task_id=task_id,
                message=record.getMessage(),
                level=record.levelname,
                logger_name=record.name,
            )
        except Exception:
            self.handleError(record)


def get_task_log_handler() -> logging.Handler:
    global _handler
    if _handler is None:
        _handler = TaskLogHandler(level=logging.INFO)
    return _handler


def install_task_log_handler(logger: Optional[logging.Logger] = None) -> None:
    target = logger or logging.getLogger()
    handler = get_task_log_handler()
    if handler not in target.handlers:
        target.addHandler(handler)


install_task_log_handler()
