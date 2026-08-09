import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from app.enmus.task_status_enums import TaskStatus
from app.services.task_log import append_task_log


logger = logging.getLogger(__name__)
_TASK_ID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _output_dir(output_dir: Optional[Union[str, Path]] = None) -> Path:
    return Path(output_dir or os.getenv("NOTE_OUTPUT_DIR", "note_results"))


def update_task_status(
    task_id: Optional[str],
    status: Union[str, TaskStatus],
    message: Optional[str] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> None:
    if not task_id:
        return

    target_dir = _output_dir(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    status_file = target_dir / f"{task_id}.status.json"
    status_value = status.value if isinstance(status, TaskStatus) else status
    try:
        default_message = TaskStatus.description(TaskStatus(status_value))
    except ValueError:
        default_message = "处理中"

    data = {
        "status": status_value,
        "message": message or default_message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        "任务状态更新 (task_id=%s, status=%s): %s",
        task_id,
        status_value,
        data["message"],
    )

    temp_file = status_file.with_suffix(".tmp")
    try:
        with temp_file.open("w", encoding="utf-8") as status_output:
            json.dump(data, status_output, ensure_ascii=False, indent=2)
        temp_file.replace(status_file)
    except Exception:
        logger.exception("写入状态文件失败 (task_id=%s)", task_id)
        temp_file.unlink(missing_ok=True)
        raise


def recover_interrupted_tasks(
    output_dir: Optional[Union[str, Path]] = None,
) -> list[str]:
    """Mark non-terminal tasks left by a previous backend process as failed."""
    target_dir = _output_dir(output_dir)
    if not target_dir.exists():
        return []

    for legacy_status in target_dir.glob("*_markdown.status.json"):
        legacy_status.unlink(missing_ok=True)

    terminal = {TaskStatus.SUCCESS.value, TaskStatus.FAILED.value}
    recovered: list[str] = []
    for status_file in target_dir.glob("*.status.json"):
        task_id = status_file.name.removesuffix(".status.json")
        if not _TASK_ID_PATTERN.fullmatch(task_id):
            continue
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") in terminal:
            continue

        result_file = target_dir / f"{task_id}.json"
        if result_file.exists():
            update_task_status(task_id, TaskStatus.SUCCESS, output_dir=target_dir)
            continue

        message = "后端进程曾重启，任务已中断，请重新生成"
        update_task_status(task_id, TaskStatus.FAILED, message=message, output_dir=target_dir)
        append_task_log(task_id, message, level="warning", logger_name=__name__)
        recovered.append(task_id)

    return recovered
