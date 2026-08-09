import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _install_stubs():
    app_mod = types.ModuleType("app")
    gpt_pkg = types.ModuleType("app.gpt")
    models_pkg = types.ModuleType("app.models")
    utils_pkg = types.ModuleType("app.utils")

    base_mod = types.ModuleType("app.gpt.base")

    class _GPT:
        pass

    base_mod.GPT = _GPT

    prompt_builder_mod = types.ModuleType("app.gpt.prompt_builder")

    def _generate_base_prompt(**_kwargs):
        return "prompt"

    prompt_builder_mod.generate_base_prompt = _generate_base_prompt

    prompt_mod = types.ModuleType("app.gpt.prompt")
    prompt_mod.BASE_PROMPT = ""
    prompt_mod.AI_SUM = ""
    prompt_mod.SCREENSHOT = ""
    prompt_mod.LINK = ""
    prompt_mod.MERGE_PROMPT = "merge"

    utils_mod = types.ModuleType("app.gpt.utils")

    def _fix_markdown(text):
        return text

    utils_mod.fix_markdown = _fix_markdown

    logger_mod = types.ModuleType("app.utils.logger")

    class _Logger:
        def info(self, *_args, **_kwargs):
            pass

        def warning(self, *_args, **_kwargs):
            pass

    logger_mod.get_logger = lambda _name: _Logger()

    request_chunker_mod = types.ModuleType("app.gpt.request_chunker")

    class _RequestChunker:
        def __init__(self, *_args, **_kwargs):
            pass

        def group_texts_by_budget(self, texts, _builder, **_kwargs):
            return [texts]

    request_chunker_mod.RequestChunker = _RequestChunker

    gpt_model_mod = types.ModuleType("app.models.gpt_model")

    class _GPTSource:
        pass

    gpt_model_mod.GPTSource = _GPTSource

    transcriber_model_mod = types.ModuleType("app.models.transcriber_model")

    class _TranscriptSegment:
        def __init__(self, **kwargs):
            self.start = kwargs.get("start", 0)
            self.end = kwargs.get("end", 0)
            self.text = kwargs.get("text", "")

    transcriber_model_mod.TranscriptSegment = _TranscriptSegment

    sys.modules["app"] = app_mod
    sys.modules["app.gpt"] = gpt_pkg
    sys.modules["app.models"] = models_pkg
    sys.modules["app.utils"] = utils_pkg
    sys.modules["app.gpt.base"] = base_mod
    sys.modules["app.gpt.prompt_builder"] = prompt_builder_mod
    sys.modules["app.gpt.prompt"] = prompt_mod
    sys.modules["app.gpt.utils"] = utils_mod
    sys.modules["app.utils.logger"] = logger_mod
    sys.modules["app.gpt.request_chunker"] = request_chunker_mod
    sys.modules["app.models.gpt_model"] = gpt_model_mod
    sys.modules["app.models.transcriber_model"] = transcriber_model_mod


def _load_universal_gpt_class():
    stub_names = [
        "app",
        "app.gpt",
        "app.models",
        "app.utils",
        "app.gpt.base",
        "app.gpt.prompt_builder",
        "app.gpt.prompt",
        "app.gpt.utils",
        "app.gpt.request_chunker",
        "app.models.gpt_model",
        "app.models.transcriber_model",
        "app.utils.logger",
    ]
    previous_modules = {name: sys.modules.get(name) for name in stub_names}
    _install_stubs()
    root = pathlib.Path(__file__).resolve().parents[1]
    module_path = root / "app" / "gpt" / "universal_gpt.py"
    spec = importlib.util.spec_from_file_location("universal_gpt", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("universal_gpt module spec not found")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module.UniversalGPT
    finally:
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


UniversalGPT = _load_universal_gpt_class()


class _FailingCompletions:
    def create(self, **_kwargs):
        raise Exception("Error code: 524 - bad_response_status_code")


class _DummyChat:
    def __init__(self):
        self.completions = _FailingCompletions()


class _DummyModels:
    @staticmethod
    def list():
        return []


class _DummyClient:
    def __init__(self):
        self.chat = _DummyChat()
        self.models = _DummyModels()


class _EventuallySuccessfulCompletions:
    def __init__(self):
        self.calls = 0
        self.timeouts = []

    def create(self, **kwargs):
        self.calls += 1
        self.timeouts.append(kwargs.get("timeout"))
        if self.calls < 3:
            raise Exception("Error code: 524 - origin_response_timeout")
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))]
        )


class _EventuallySuccessfulClient:
    def __init__(self):
        self.chat = types.SimpleNamespace(completions=_EventuallySuccessfulCompletions())
        self.models = _DummyModels()


class TestUniversalGPTCheckpoint(unittest.TestCase):
    def test_retry_is_bounded_and_uses_per_request_timeout(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_RETRY_ATTEMPTS": "3",
                "OPENAI_RETRY_BACKOFF_SECONDS": "0",
                "OPENAI_REQUEST_TIMEOUT_SECONDS": "12",
                "OPENAI_RETRY_MAX_ELAPSED_SECONDS": "30",
            },
        ):
            client = _EventuallySuccessfulClient()
            gpt = UniversalGPT(client, model="mock-model")

            response = gpt._chat_completion_create([{"role": "user", "content": "test"}])

        self.assertEqual(response.choices[0].message.content, "ok")
        self.assertEqual(client.chat.completions.calls, 3)
        self.assertTrue(all(0 < value <= 12 for value in client.chat.completions.timeouts))

    def test_retry_exhaustion_returns_concise_error(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_RETRY_ATTEMPTS": "2",
                "OPENAI_RETRY_BACKOFF_SECONDS": "0",
                "OPENAI_REQUEST_TIMEOUT_SECONDS": "12",
                "OPENAI_RETRY_MAX_ELAPSED_SECONDS": "30",
            },
        ):
            gpt = UniversalGPT(_DummyClient(), model="mock-model")
            with self.assertRaisesRegex(RuntimeError, "GPT 请求连续失败 2 次"):
                gpt._chat_completion_create([{"role": "user", "content": "test"}])

    def test_merge_524_error_persists_checkpoint(self):
        original_attempts = os.environ.get("OPENAI_RETRY_ATTEMPTS")
        os.environ["OPENAI_RETRY_ATTEMPTS"] = "1"
        gpt = UniversalGPT(_DummyClient(), model="mock-model")
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                gpt.checkpoint_dir = Path(tmp_dir)

                with self.assertRaises(Exception):
                    gpt._merge_partials(["part-a", "part-b"], "task-1", "sig-1")

                checkpoint_path = gpt._checkpoint_path("task-1")
                self.assertTrue(checkpoint_path.exists())
                payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["phase"], "merge")
                self.assertEqual(payload["partials"], ["part-a", "part-b"])
        finally:
            if original_attempts is None:
                os.environ.pop("OPENAI_RETRY_ATTEMPTS", None)
            else:
                os.environ["OPENAI_RETRY_ATTEMPTS"] = original_attempts


if __name__ == "__main__":
    unittest.main()
