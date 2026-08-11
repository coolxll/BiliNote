import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.enmus.task_status_enums import TaskStatus
from app.services.task_log import read_task_logs
from app.services.task_status import recover_interrupted_tasks, update_task_status


TASK_ID = "864c7a62-b4cc-4c8a-9591-575c2365c7fd"


class TestTaskStatusRecovery(unittest.TestCase):
    def test_marks_interrupted_task_failed_and_removes_legacy_status(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"NOTE_OUTPUT_DIR": temp_dir}
        ):
            update_task_status(TASK_ID, TaskStatus.SUMMARIZING, output_dir=temp_dir)
            legacy = Path(temp_dir) / f"{TASK_ID}_markdown.status.json"
            legacy.write_text("{}", encoding="utf-8")

            recovered = recover_interrupted_tasks(temp_dir)

            status = json.loads(
                (Path(temp_dir) / f"{TASK_ID}.status.json").read_text(encoding="utf-8")
            )
            self.assertEqual(recovered, [TASK_ID])
            self.assertEqual(status["status"], TaskStatus.FAILED.value)
            self.assertIn("后端进程曾重启", status["message"])
            self.assertFalse(legacy.exists())
            self.assertIn("任务已中断", read_task_logs(TASK_ID)[-1]["message"])

    def test_recovers_completed_result_as_success(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"NOTE_OUTPUT_DIR": temp_dir}
        ):
            update_task_status(TASK_ID, TaskStatus.SAVING, output_dir=temp_dir)
            (Path(temp_dir) / f"{TASK_ID}.json").write_text("{}", encoding="utf-8")

            recovered = recover_interrupted_tasks(temp_dir)

            status = json.loads(
                (Path(temp_dir) / f"{TASK_ID}.status.json").read_text(encoding="utf-8")
            )
            self.assertEqual(recovered, [])
            self.assertEqual(status["status"], TaskStatus.SUCCESS.value)


if __name__ == "__main__":
    unittest.main()
