import os
import unittest
from unittest.mock import Mock, patch

from app.utils.openai_client import build_openai_client


class TestOpenAIClientRetryConfig(unittest.TestCase):
    def test_sdk_retries_are_disabled_by_default(self):
        fake_client = Mock()
        with patch("app.utils.openai_client.OpenAI", return_value=fake_client) as openai_cls, patch(
            "app.utils.openai_client.ProxyConfigManager.get_proxy_url",
            return_value=None,
        ), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_SDK_MAX_RETRIES", None)

            client = build_openai_client("test-key", "https://example.com/v1")

        self.assertIs(client, fake_client)
        self.assertEqual(openai_cls.call_args.kwargs["max_retries"], 0)

    def test_sdk_retry_override_is_respected(self):
        with patch("app.utils.openai_client.OpenAI") as openai_cls, patch(
            "app.utils.openai_client.ProxyConfigManager.get_proxy_url",
            return_value=None,
        ), patch.dict(os.environ, {"OPENAI_SDK_MAX_RETRIES": "1"}):
            build_openai_client("test-key", "https://example.com/v1")

        self.assertEqual(openai_cls.call_args.kwargs["max_retries"], 1)
