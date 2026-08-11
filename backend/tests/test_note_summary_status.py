import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.enmus.task_status_enums import TaskStatus
from app.services.note import NoteGenerator


TASK_ID = "864c7a62-b4cc-4c8a-9591-575c2365c7fd"


class TestNoteSummaryStatus(unittest.TestCase):
    def test_summary_uses_main_task_id_for_status_and_checkpoint(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator._update_status = Mock()
        gpt = Mock()
        gpt.summarize.return_value = "# result"
        audio_meta = SimpleNamespace(title="title", raw_info={"tags": []})
        transcript = SimpleNamespace(segments=[])

        with tempfile.TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / f"{TASK_ID}_markdown.md"
            result = generator._summarize_text(
                task_id=TASK_ID,
                audio_meta=audio_meta,
                transcript=transcript,
                gpt=gpt,
                markdown_cache_file=markdown_path,
                link=False,
                screenshot=False,
                formats=[],
                style=None,
                extras=None,
                video_img_urls=[],
            )

        generator._update_status.assert_called_once_with(TASK_ID, TaskStatus.SUMMARIZING)
        source = gpt.summarize.call_args.args[0]
        self.assertEqual(source.checkpoint_key, TASK_ID)
        self.assertEqual(result, "# result")
