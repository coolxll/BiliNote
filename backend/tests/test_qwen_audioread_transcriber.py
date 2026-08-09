import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.transcriber.qwen_audioread import QwenAudioReadTranscriber, parse_audioread_markdown


class FakeResponse:
    def __init__(self, payload=None, *, text="", status_code=200):
        self.payload = payload
        self.text = text
        self.status_code = status_code
        self.ok = 200 <= status_code < 300

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.poll_count = 0

    def post(self, *args, **kwargs):
        return FakeResponse({"job_id": "job-1", "status": "queued"}, status_code=202)

    def get(self, url, **kwargs):
        if url.endswith("/file"):
            return FakeResponse(text="00:00 - 00:10\n第一段\n\n00:10\n第二段")
        self.poll_count += 1
        if self.poll_count == 1:
            return FakeResponse({"job_id": "job-1", "status": "running"})
        return FakeResponse({"job_id": "job-1", "status": "succeeded", "markdown_filename": "result.md"})


class AudioReadMarkdownTests(unittest.TestCase):
    def test_timestamp_markdown_builds_segments(self):
        segments, mode = parse_audioread_markdown(
            "00:00 - 00:05\n第一段\n\n00:05\n第二段",
            duration=12,
        )
        self.assertEqual(mode, "timestamp")
        self.assertEqual([segment.text for segment in segments], ["第一段", "第二段"])
        self.assertEqual(segments[0].end, 5)
        self.assertEqual(segments[1].end, 12)

    def test_plain_markdown_uses_paragraph_fallback(self):
        segments, mode = parse_audioread_markdown("# 标题\n\n第一段内容\n\n第二段内容", duration=60)
        self.assertEqual(mode, "paragraph-fallback")
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[-1].end, 60)

    def test_transcriber_submits_polls_and_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "sample.mp3"
            audio.write_bytes(b"audio")
            with patch.dict(
                os.environ,
                {
                    "QWEN_AUDIOREAD_API_KEY": "secret",
                    "QWEN_AUDIOREAD_BASE_URL": "http://audioread:8000",
                    "QWEN_AUDIOREAD_POLL_INTERVAL_SECONDS": "5",
                },
                clear=False,
            ), patch("app.transcriber.qwen_audioread.time.sleep"), patch(
                "app.transcriber.qwen_audioread._probe_duration", return_value=20
            ):
                result = QwenAudioReadTranscriber(session=FakeSession()).transcript(str(audio))

        self.assertEqual(result.full_text, "第一段 第二段")
        self.assertEqual(result.raw["provider"], "qwen-audioread")
        self.assertEqual(result.raw["job_id"], "job-1")
