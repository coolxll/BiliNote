import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.enmus.task_status_enums import TaskStatus
from app.routers import note as note_router


TASK_ID = "325f2899-dbc4-4de3-9d38-50b01bb5b570"


class TestTaskStatusApi(unittest.TestCase):
    def test_failed_retry_returns_business_status_and_existing_result(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            note_router, "NOTE_OUTPUT_DIR", temp_dir
        ):
            output_dir = Path(temp_dir)
            (output_dir / f"{TASK_ID}.status.json").write_text(
                json.dumps(
                    {
                        "status": TaskStatus.FAILED.value,
                        "message": "retry timed out",
                        "updated_at": "2026-08-09T13:40:39+00:00",
                    }
                ),
                encoding="utf-8",
            )
            (output_dir / f"{TASK_ID}.json").write_text(
                json.dumps({"markdown": "# previous result"}),
                encoding="utf-8",
            )

            response = note_router.get_task_status(TASK_ID)
            payload = json.loads(response.body)

            self.assertEqual(payload["code"], 0)
            self.assertEqual(payload["data"]["status"], TaskStatus.FAILED.value)
            self.assertTrue(payload["data"]["has_result"])
            self.assertEqual(payload["data"]["result"]["markdown"], "# previous result")


if __name__ == "__main__":
    unittest.main()
