import json
import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVIDER_PATH = BACKEND_ROOT / "app" / "providers" / "xiaoyuzhou.py"
SPEC = importlib.util.spec_from_file_location("xiaoyuzhou_provider", PROVIDER_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError("xiaoyuzhou provider module spec not found")
provider_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = provider_module
SPEC.loader.exec_module(provider_module)
XiaoyuzhouProvider = provider_module.XiaoyuzhouProvider


EPISODE_ID = "69b4d2f9f8b8079bfa3ae7f2"
EPISODE_URL = f"https://www.xiaoyuzhoufm.com/episode/{EPISODE_ID}"
AUDIO_URL = "https://media.xyzcdn.net/podcast/test.m4a"


def build_page(episode):
    payload = {"props": {"pageProps": {"episode": episode}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'


class TestXiaoyuzhouDownloader(unittest.TestCase):
    def test_rejects_non_xiaoyuzhou_host(self):
        malicious_url = f"https://example.com/?next=xiaoyuzhoufm.com/episode/{EPISODE_ID}"

        self.assertIsNone(XiaoyuzhouProvider.extract_episode_id(malicious_url))

    def test_parses_public_episode_metadata(self):
        episode = {
            "eid": EPISODE_ID,
            "title": "Test episode",
            "duration": 120,
            "enclosure": {"url": AUDIO_URL},
        }

        parsed = XiaoyuzhouProvider.parse_episode_page(build_page(episode))

        self.assertEqual(parsed["eid"], EPISODE_ID)
        self.assertEqual(parsed["enclosure"]["url"], AUDIO_URL)

    def test_falls_back_to_dehydrated_state(self):
        episode = {"eid": EPISODE_ID, "media": {"source": {"url": AUDIO_URL}}}
        payload = {
            "props": {
                "pageProps": {
                    "dehydratedState": {
                        "queries": [{"state": {"data": {"episode": episode}}}]
                    }
                }
            }
        }
        html = f'<script id="__NEXT_DATA__">{json.dumps(payload)}</script>'

        parsed = XiaoyuzhouProvider.parse_episode_page(html)

        self.assertEqual(parsed["media"]["source"]["url"], AUDIO_URL)

    @patch("xiaoyuzhou_provider.requests.get")
    def test_downloads_audio_and_returns_metadata(self, mock_get):
        episode = {
            "eid": EPISODE_ID,
            "title": "Test episode",
            "duration": 120,
            "enclosure": {"url": AUDIO_URL},
            "podcast": {"image": {"picUrl": "https://image.xyzcdn.net/cover.png"}},
        }
        page_response = Mock()
        page_response.text = build_page(episode)
        page_response.raise_for_status.return_value = None
        audio_response = Mock()
        audio_response.raise_for_status.return_value = None
        audio_response.iter_content.return_value = [b"audio-data"]
        mock_get.side_effect = [page_response, audio_response]

        with tempfile.TemporaryDirectory() as output_dir:
            provider = XiaoyuzhouProvider()
            episode = provider.resolve(EPISODE_URL)
            audio_path = provider.download_audio(episode, output_dir)

            self.assertEqual(episode.episode_id, EPISODE_ID)
            self.assertEqual(episode.title, "Test episode")
            self.assertTrue(pathlib.Path(audio_path).is_file())
            self.assertEqual(pathlib.Path(audio_path).read_bytes(), b"audio-data")


if __name__ == "__main__":
    unittest.main()
