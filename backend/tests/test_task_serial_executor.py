import importlib.util
import pathlib
import threading
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "services" / "task_serial_executor.py"
spec = importlib.util.spec_from_file_location("task_executor", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("task executor module spec not found")
task_executor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task_executor_module)
ConcurrentTaskExecutor = task_executor_module.ConcurrentTaskExecutor


class TestConcurrentTaskExecutor(unittest.TestCase):
    @staticmethod
    def _measure_peak_active(max_workers: int, task_count: int) -> int:
        executor = ConcurrentTaskExecutor(max_workers=max_workers)
        state_lock = threading.Lock()
        state = {"active": 0, "peak_active": 0}

        def work():
            with state_lock:
                state["active"] += 1
                state["peak_active"] = max(state["peak_active"], state["active"])
            time.sleep(0.05)
            with state_lock:
                state["active"] -= 1

        threads = [threading.Thread(target=lambda: executor.run(work)) for _ in range(task_count)]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            return state["peak_active"]
        finally:
            executor.shutdown()

    def test_executor_runs_tasks_up_to_worker_limit(self):
        self.assertEqual(self._measure_peak_active(max_workers=2, task_count=4), 2)

    def test_single_worker_preserves_serial_execution(self):
        self.assertEqual(self._measure_peak_active(max_workers=1, task_count=3), 1)

    def test_run_returns_result_and_propagates_exception(self):
        executor = ConcurrentTaskExecutor(max_workers=1)
        try:
            self.assertEqual(executor.run(lambda value: value * 2, 21), 42)
            with self.assertRaisesRegex(RuntimeError, "task failed"):
                executor.run(lambda: (_ for _ in ()).throw(RuntimeError("task failed")))
        finally:
            executor.shutdown()

    def test_rejects_invalid_worker_count(self):
        for value in (0, -1, "invalid"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ConcurrentTaskExecutor(max_workers=value)


if __name__ == "__main__":
    unittest.main()
