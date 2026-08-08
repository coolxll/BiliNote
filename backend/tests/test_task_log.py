import importlib.util
import logging
import os
import pathlib
import sys
import tempfile
import unittest


BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = BACKEND_ROOT / "app" / "services" / "task_log.py"
SPEC = importlib.util.spec_from_file_location("task_log_test_module", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError("task_log module spec not found")
task_log = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = task_log
SPEC.loader.exec_module(task_log)


class TestTaskLog(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_output_dir = os.environ.get("NOTE_OUTPUT_DIR")
        os.environ["NOTE_OUTPUT_DIR"] = self.temp_dir.name

    def tearDown(self):
        if self.previous_output_dir is None:
            os.environ.pop("NOTE_OUTPUT_DIR", None)
        else:
            os.environ["NOTE_OUTPUT_DIR"] = self.previous_output_dir
        self.temp_dir.cleanup()

    def test_records_context_logs_and_redacts_secrets(self):
        task_id = "task-123"
        logger = logging.getLogger("app.test.task_log")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = task_log.get_task_log_handler()
        logger.addHandler(handler)
        try:
            task_log.append_task_log(task_id, "api_key=secret-value")
            with task_log.task_log_context(task_id):
                logger.info("正在下载音频")
        finally:
            logger.removeHandler(handler)

        entries = task_log.read_task_logs(task_id)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["message"], "api_key=***")
        self.assertEqual(entries[1]["message"], "正在下载音频")
        self.assertEqual(entries[1]["logger"], "app.test.task_log")

    def test_limits_returned_entries(self):
        task_id = "task-limit"
        for index in range(5):
            task_log.append_task_log(task_id, f"entry-{index}")

        entries = task_log.read_task_logs(task_id, limit=2)

        self.assertEqual([entry["message"] for entry in entries], ["entry-3", "entry-4"])

    def test_deduplicates_record_when_handler_is_on_logger_and_root(self):
        task_id = "task-deduplicate"
        logger = logging.getLogger("app.test.duplicate")
        logger.setLevel(logging.INFO)
        logger.propagate = True
        handler = task_log.get_task_log_handler()
        logger.addHandler(handler)
        task_log.install_task_log_handler()
        try:
            with task_log.task_log_context(task_id):
                logger.info("只记录一次")
        finally:
            logger.removeHandler(handler)

        entries = task_log.read_task_logs(task_id)
        self.assertEqual([entry["message"] for entry in entries], ["只记录一次"])


if __name__ == "__main__":
    unittest.main()
