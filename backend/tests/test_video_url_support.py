import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module(name, relative_path):
    module_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"{name} module spec not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


url_parser = _load_module("url_parser", pathlib.Path("app") / "utils" / "url_parser.py")
video_url_validator = _load_module(
    "video_url_validator",
    pathlib.Path("app") / "validators" / "video_url_validator.py",
)


class TestVideoUrlSupport(unittest.TestCase):
    def test_extract_youtube_video_id_from_supported_url_shapes(self):
        expected_id = "dQw4w9WgXcQ"

        cases = [
            f"https://www.youtube.com/watch?v={expected_id}",
            f"https://youtu.be/{expected_id}",
            f"https://www.youtube.com/shorts/{expected_id}",
        ]

        for url in cases:
            with self.subTest(url=url):
                self.assertEqual(
                    url_parser.extract_video_id(url, "youtube"),
                    expected_id,
                )

    def test_accepts_youtube_shorts_url(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"

        self.assertTrue(video_url_validator.is_supported_video_url(url))

    def test_accepts_xiaoyuzhou_episode_url_and_extracts_id(self):
        episode_id = "69b4d2f9f8b8079bfa3ae7f2"
        url = f"https://www.xiaoyuzhoufm.com/episode/{episode_id}"

        self.assertTrue(video_url_validator.is_supported_video_url(url))
        self.assertEqual(url_parser.extract_video_id(url, "xiaoyuzhou"), episode_id)

    def test_rejects_xiaoyuzhou_id_embedded_in_another_host(self):
        url = "https://example.com/?next=xiaoyuzhoufm.com/episode/69b4d2f9f8b8079bfa3ae7f2"

        self.assertFalse(video_url_validator.is_supported_video_url(url))
        self.assertIsNone(url_parser.extract_video_id(url, "xiaoyuzhou"))

    def test_accepts_apple_podcasts_episode_url_and_extracts_episode_id(self):
        url = "https://podcasts.apple.com/cn/podcast/example/id1582119137?i=1000774969980"

        self.assertTrue(video_url_validator.is_supported_video_url(url))
        self.assertEqual(
            url_parser.extract_video_id(url, "apple_podcasts"),
            "1000774969980",
        )

    def test_rejects_apple_show_url_without_episode_query(self):
        url = "https://podcasts.apple.com/cn/podcast/example/id1582119137"

        self.assertFalse(video_url_validator.is_supported_video_url(url))
        self.assertIsNone(url_parser.extract_video_id(url, "apple_podcasts"))

    def test_rejects_spoofed_apple_podcasts_host(self):
        url = "https://example.com/cn/podcast/example/id1582119137?i=1000774969980"

        self.assertFalse(video_url_validator.is_supported_video_url(url))
        self.assertIsNone(url_parser.extract_video_id(url, "apple_podcasts"))


if __name__ == "__main__":
    unittest.main()
