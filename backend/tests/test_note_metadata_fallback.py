import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.note import NoteGenerator


class TestNoteMetadataFallback(unittest.TestCase):
    def test_existing_transcript_does_not_download_audio_when_metadata_fails(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        downloader = Mock()
        downloader.download.side_effect = RuntimeError("metadata unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "task_audio.json"
            with patch.object(generator, "_update_status"):
                result = generator._download_media(
                    downloader=downloader,
                    video_url="https://www.bilibili.com/video/BV1csuF6bEGf",
                    quality="medium",
                    audio_cache_file=cache_file,
                    status_phase="downloading",
                    platform="bilibili",
                    output_path=temp_dir,
                    screenshot=False,
                    video_understanding=False,
                    video_interval=0,
                    grid_size=[],
                    skip_download=True,
                )

            self.assertEqual(downloader.download.call_count, 1)
            self.assertTrue(downloader.download.call_args.kwargs["skip_download"])
            self.assertEqual(result.file_path, "")
            self.assertEqual(result.video_id, "BV1csuF6bEGf")
            self.assertEqual(result.title, "BV1csuF6bEGf")
            self.assertTrue(result.raw_info["metadata_fallback"])

            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            self.assertEqual(cached["video_id"], "BV1csuF6bEGf")
            self.assertTrue(cached["raw_info"]["metadata_fallback"])


if __name__ == "__main__":
    unittest.main()
