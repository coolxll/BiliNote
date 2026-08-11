import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app.podcasts.apple import ApplePodcastsAdapter, ApplePodcastsClient
from app.podcasts.cache import BoundedTTLCache
from app.podcasts.models import PodcastCatalogPage
from app.podcasts.xiaoyuzhou import XiaoyuzhouPodcastAdapter
from app.providers.apple_podcasts import ApplePodcastsProvider, parse_apple_episode_url
from app.routers.podcasts import DiscoverRequest, discover


PODCAST_ID = "1582119137"
EPISODE_ID = "1000774969980"
EPISODE_URL = (
    f"https://podcasts.apple.com/cn/podcast/example/id{PODCAST_ID}?i={EPISODE_ID}"
)
AUDIO_URL = "https://audio.example.com/episode.mp3"


class FakeResponse:
    def __init__(self, payload=None, content=b"audio"):
        self._payload = payload or {}
        self._content = content
        self.status_code = 200

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        del chunk_size
        return [self._content]


def apple_episode(track_id=EPISODE_ID):
    return {
        "wrapperType": "podcastEpisode",
        "trackId": int(track_id),
        "collectionId": int(PODCAST_ID),
        "trackName": "Test episode",
        "collectionName": "Test podcast",
        "episodeUrl": AUDIO_URL,
        "trackViewUrl": EPISODE_URL,
        "trackTimeMillis": 125000,
        "episodeFileExtension": "mp3",
    }


def apple_top_episode(
    episode_id=EPISODE_ID,
    podcast_id=PODCAST_ID,
    title="Top episode",
):
    return {
        "artistName": "Top author",
        "id": episode_id,
        "name": title,
        "artworkUrl100": "https://image.example.com/100x100bb.jpg",
        "genres": [{"name": "Technology"}],
        "url": (
            "https://podcasts.apple.com/cn/podcast/example/"
            f"id{podcast_id}?i={episode_id}"
        ),
    }


class TestPodcastCatalog(unittest.TestCase):
    def test_apple_episode_url_requires_exact_host_show_and_episode_ids(self):
        self.assertEqual(
            parse_apple_episode_url(EPISODE_URL),
            (PODCAST_ID, EPISODE_ID, "cn"),
        )
        self.assertIsNone(
            parse_apple_episode_url(
                f"https://podcasts.apple.com/cn/podcast/example/id{PODCAST_ID}"
            )
        )
        self.assertIsNone(
            parse_apple_episode_url(
                f"https://example.com/cn/podcast/example/id{PODCAST_ID}?i={EPISODE_ID}"
            )
        )
        self.assertIsNone(
            parse_apple_episode_url(
                f"http://podcasts.apple.com/cn/podcast/example/id{PODCAST_ID}?i={EPISODE_ID}"
            )
        )

    def test_apple_lookup_matches_exact_episode_and_never_falls_back(self):
        session = Mock()
        session.get.return_value = FakeResponse(
            {"results": [apple_episode("1000000000001"), apple_episode()]}
        )
        client = ApplePodcastsClient(session)

        result = client.resolve_episode(PODCAST_ID, EPISODE_ID)

        self.assertEqual(str(result["trackId"]), EPISODE_ID)
        with self.assertRaises(LookupError):
            client.resolve_episode(PODCAST_ID, "1000000000002")

    def test_apple_top_episode_feed_is_batch_enriched_by_exact_ids(self):
        unmatched_id = "1000774000000"
        session = Mock()
        session.get.side_effect = [
            FakeResponse(
                {
                    "feed": {
                        "results": [
                            apple_top_episode(),
                            apple_top_episode(unmatched_id, title="Fallback episode"),
                        ]
                    }
                }
            ),
            FakeResponse(
                {
                    "results": [
                        {"wrapperType": "track", "trackId": int(PODCAST_ID)},
                        apple_episode(),
                        apple_episode(unmatched_id) | {"collectionId": 999999999},
                    ]
                }
            ),
        ]
        client = ApplePodcastsClient(session)

        results = client.top("episode", "cn", 2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["episodeUrl"], AUDIO_URL)
        self.assertNotIn("episodeUrl", results[1])
        self.assertEqual(results[1]["trackName"], "Fallback episode")
        feed_call, lookup_call = session.get.call_args_list
        self.assertTrue(feed_call.args[0].endswith("/podcast-episodes.json"))
        self.assertEqual(lookup_call.args[0], "https://itunes.apple.com/lookup")
        self.assertEqual(lookup_call.kwargs["params"]["id"], PODCAST_ID)
        self.assertEqual(lookup_call.kwargs["params"]["limit"], 10)

    def test_apple_top_episode_ids_are_parsed_from_official_url(self):
        self.assertEqual(
            ApplePodcastsClient._top_episode_ids(apple_top_episode()),
            (PODCAST_ID, EPISODE_ID),
        )
        self.assertIsNone(
            ApplePodcastsClient._top_episode_ids(
                apple_top_episode() | {"url": "https://example.com/podcast/id1?i=2"}
            )
        )

    def test_apple_unmatched_top_episode_keeps_basic_fields(self):
        item = ApplePodcastsAdapter.normalize_episode(
            {
                "trackId": EPISODE_ID,
                "collectionId": PODCAST_ID,
                "trackName": "Fallback episode",
                "artistName": "Fallback author",
                "artworkUrl100": "https://image.example.com/100x100bb.jpg",
                "trackViewUrl": EPISODE_URL,
            }
        )

        self.assertEqual(item.title, "Fallback episode")
        self.assertEqual(item.author, "Fallback author")
        self.assertEqual(item.podcast_id, PODCAST_ID)
        self.assertEqual(item.canonical_url, EPISODE_URL)
        self.assertTrue(item.is_private)

    def test_apple_catalog_dto_does_not_expose_audio_url(self):
        item = ApplePodcastsAdapter.normalize_episode(apple_episode())

        self.assertNotIn("episodeUrl", item.model_dump_json())
        self.assertEqual(item.id, EPISODE_ID)
        self.assertFalse(item.is_private)

    @patch("app.providers.apple_podcasts.requests.get")
    def test_apple_provider_downloads_public_audio_with_sanitized_metadata(self, mock_get):
        client = Mock()
        client.resolve_episode.return_value = apple_episode()
        mock_get.return_value = FakeResponse(content=b"audio-data")
        provider = ApplePodcastsProvider(client)

        with tempfile.TemporaryDirectory() as output_dir:
            episode = provider.resolve(EPISODE_URL)
            audio_path = provider.download_audio(episode, output_dir)

            self.assertEqual(Path(audio_path).read_bytes(), b"audio-data")
            self.assertNotIn("episodeUrl", episode.raw_info)
            self.assertNotIn(AUDIO_URL, str(episode.raw_info))

    def test_xiaoyuzhou_private_episode_is_normalized_without_media_url(self):
        item = XiaoyuzhouPodcastAdapter.normalize_episode(
            {
                "eid": "69b4d2f9f8b8079bfa3ae7f2",
                "pid": "5e4243cd418a84a0469573fb",
                "title": "Private episode",
                "isPrivateMedia": True,
                "enclosure": {"url": "https://audio.example.com/private.m4a"},
                "podcast": {"pid": "5e4243cd418a84a0469573fb", "title": "Show"},
            }
        )

        self.assertTrue(item.is_private)
        self.assertNotIn("audio.example.com", item.model_dump_json())

    def test_xiaoyuzhou_show_discovery_preserves_first_occurrence_order(self):
        payload = [
            {
                "eid": "episode-1",
                "podcast": {"pid": "show-b", "title": "Show B"},
            },
            {
                "module": {
                    "eid": "episode-2",
                    "podcast": {"pid": "show-a", "title": "Show A"},
                }
            },
            {
                "eid": "episode-3",
                "podcast": {"pid": "show-b", "title": "Show B duplicate"},
            },
        ]

        items = XiaoyuzhouPodcastAdapter._dedupe_shows_from_episodes(payload, 10)

        self.assertEqual([item.id for item in items], ["show-b", "show-a"])
        self.assertEqual([item.kind for item in items], ["show", "show"])

    def test_discover_uses_source_native_entity_defaults(self):
        cases = [
            ("apple_podcasts", "top", "show"),
            ("xiaoyuzhou", "personalized", "episode"),
        ]
        for source, mode, expected_entity in cases:
            with self.subTest(source=source):
                adapter = Mock()
                adapter.discover.return_value = PodcastCatalogPage()
                with patch("app.routers.podcasts.get_podcast_adapter", return_value=adapter):
                    discover(DiscoverRequest(source=source, mode=mode))
                adapter.discover.assert_called_once_with(
                    mode,
                    expected_entity,
                    "cn",
                    None,
                    20,
                )

    def test_discover_rejects_invalid_entity(self):
        with self.assertRaises(ValidationError):
            DiscoverRequest(source="apple_podcasts", mode="top", entity="album")

    def test_cache_is_bounded_and_expired_entries_are_not_returned(self):
        cache = BoundedTTLCache[int](max_entries=2)
        cache.set("a", 1, 60)
        cache.set("b", 2, 60)
        cache.set("c", 3, 60)

        self.assertIsNone(cache.get("a"))
        self.assertEqual(len(cache), 2)
        cache.set("expired", 4, 0)
        self.assertIsNone(cache.get("expired"))


if __name__ == "__main__":
    unittest.main()
