import os
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


class ConcurrentTaskExecutor:
    """使用有界线程池执行后台任务。"""

    def __init__(self, max_workers: int | None = None):
        configured_workers = max_workers if max_workers is not None else os.getenv("TASK_MAX_WORKERS", "3")
        try:
            self._max_workers = int(configured_workers)
        except (TypeError, ValueError) as exc:
            raise ValueError("TASK_MAX_WORKERS 必须是正整数") from exc
        if self._max_workers < 1:
            raise ValueError("TASK_MAX_WORKERS 必须大于等于 1")
        self._pool = ThreadPoolExecutor(max_workers=self._max_workers)

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        future: Future[Any] = self._pool.submit(fn, *args, **kwargs)
        return future.result()

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)


# 新代码使用真实语义名称；旧名称保留以兼容已有导入。
task_executor = ConcurrentTaskExecutor()
SerialTaskExecutor = ConcurrentTaskExecutor
task_serial_executor = task_executor
