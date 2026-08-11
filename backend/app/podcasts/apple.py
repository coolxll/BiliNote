import logging
import threading
import time
from collections import deque
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests

from app.podcasts.base import PodcastSourceAdapter
from app.podcasts.cache import BoundedTTLCache
from app.podcasts.models import PodcastCatalogItem, PodcastCatalogPage


logger = logging.getLogger(__name__)

APPLE_SEARCH_URL = "https://itunes.apple.com/search"
APPLE_LOOKUP_URL = "https://itunes.apple.com/lookup"
APPLE_TOP_URL = "https://rss.marketingtools.apple.com/api/v2/{market}/podcasts/top/{limit}/{feed}.json"
APPLE_TTL_SECONDS = 15 * 60
APPLE_EPISODE_LOOKUP_LIMIT = 200
APPLE_TOP_EPISODE_LOOKUP_LIMIT = 10


class ApplePodcastsClient:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.cache: BoundedTTLCache[Any] = BoundedTTLCache(max_entries=256)
        self.episode_cache = self.cache
        self._request_times: deque[float] = deque()
        self._rate_limit_lock = threading.RLock()

    def _wait_for_rate_limit(self) -> None:
        while True:
            with self._rate_limit_lock:
                now = time.monotonic()
                while self._request_times and now - self._request_times[0] >= 60:
                    self._request_times.popleft()
                if len(self._request_times) < 20:
                    self._request_times.append(now)
                    return
                wait_seconds = max(0.05, 60 - (now - self._request_times[0]))
            time.sleep(wait_seconds)

    def _get_json(self, url: str, *, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        self._wait_for_rate_limit()
        response = self.session.get(url, params=params, timeout=(10, 30))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Apple Podcasts 返回了无效数据")
        return payload

    @staticmethod
    def _top_episode_ids(item: dict[str, Any]) -> Optional[tuple[str, str]]:
        url = item.get("url")
        if not isinstance(url, str):
            return None
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "podcasts.apple.com":
            return None
        path_parts = [part for part in parsed.path.split("/") if part]
        if not path_parts or not path_parts[-1].startswith("id"):
            return None
        podcast_id = path_parts[-1][2:]
        episode_ids = parse_qs(parsed.query).get("i", [])
        if not podcast_id.isdigit() or len(episode_ids) != 1 or not episode_ids[0].isdigit():
            return None
        return podcast_id, episode_ids[0]

    def _top_feed(self, entity: str, market: str, limit: int) -> list[dict[str, Any]]:
        feed = "podcasts" if entity == "show" else "podcast-episodes"
        payload = self._get_json(
            APPLE_TOP_URL.format(market=market, limit=limit, feed=feed)
        )
        results = payload.get("feed", {}).get("results", [])
        if not isinstance(results, list) or not results:
            label = "节目" if entity == "show" else "单集"
            raise RuntimeError(f"Apple Podcasts 热门{label}结果为空")
        return results

    def _enrich_top_episodes(
        self,
        feed_items: list[dict[str, Any]],
        market: str,
    ) -> list[dict[str, Any]]:
        parsed_items: list[tuple[dict[str, Any], str, str]] = []
        podcast_ids: list[str] = []
        seen_podcast_ids: set[str] = set()
        for item in feed_items:
            if not isinstance(item, dict):
                continue
            ids = self._top_episode_ids(item)
            if ids is None:
                continue
            podcast_id, episode_id = ids
            parsed_items.append((item, podcast_id, episode_id))
            if podcast_id not in seen_podcast_ids:
                seen_podcast_ids.add(podcast_id)
                podcast_ids.append(podcast_id)

        matches: dict[tuple[str, str], dict[str, Any]] = {}
        if podcast_ids:
            payload = self._get_json(
                APPLE_LOOKUP_URL,
                params={
                    "id": ",".join(podcast_ids),
                    "country": market,
                    "media": "podcast",
                    "entity": "podcastEpisode",
                    "limit": APPLE_TOP_EPISODE_LOOKUP_LIMIT,
                },
            )
            results = payload.get("results", [])
            if not isinstance(results, list):
                raise RuntimeError("Apple Podcasts 单集补全结果格式无效")
            for result in results:
                if (
                    isinstance(result, dict)
                    and result.get("wrapperType") == "podcastEpisode"
                    and result.get("collectionId") is not None
                    and result.get("trackId") is not None
                ):
                    matches[(str(result["collectionId"]), str(result["trackId"]))] = result

        enriched: list[dict[str, Any]] = []
        matched_episodes: list[dict[str, Any]] = []
        for item, podcast_id, episode_id in parsed_items:
            basic = {
                "trackId": episode_id,
                "collectionId": podcast_id,
                "trackName": item.get("name"),
                "artistName": item.get("artistName"),
                "artworkUrl100": item.get("artworkUrl100"),
                "genres": item.get("genres"),
                "trackViewUrl": item.get("url"),
            }
            match = matches.get((podcast_id, episode_id))
            if match is None:
                enriched.append(basic)
                continue
            merged = {**basic, **match}
            merged["trackId"] = episode_id
            merged["collectionId"] = podcast_id
            enriched.append(merged)
            matched_episodes.append(merged)
        self.remember_episodes(matched_episodes)
        return enriched

    def top(self, entity: str, market: str, limit: int) -> list[dict[str, Any]]:
        if entity not in {"show", "episode"}:
            raise ValueError(f"Apple Podcasts 不支持实体类型: {entity}")
        key = f"top:{entity}:{market}:{limit}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        results = self._top_feed(entity, market, limit)
        if entity == "episode":
            results = self._enrich_top_episodes(results, market)
        if not results:
            raise RuntimeError("Apple Podcasts 热门结果无法解析")
        self.cache.set(key, results, APPLE_TTL_SECONDS)
        return results

    def search(self, entity: str, query: str, market: str, limit: int) -> list[dict[str, Any]]:
        key = f"search:{entity}:{market}:{limit}:{query}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        payload = self._get_json(
            APPLE_SEARCH_URL,
            params={
                "term": query,
                "country": market,
                "media": "podcast",
                "entity": "podcast" if entity == "show" else "podcastEpisode",
                "limit": limit,
            },
        )
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise RuntimeError("Apple Podcasts 搜索结果格式无效")
        if results:
            self.cache.set(key, results, APPLE_TTL_SECONDS)
            self.remember_episodes(results)
        return results

    def lookup_show(self, podcast_id: str, market: str) -> dict[str, Any]:
        key = f"show:{market}:{podcast_id}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        payload = self._get_json(
            APPLE_LOOKUP_URL,
            params={"id": podcast_id, "country": market, "entity": "podcast"},
        )
        results = payload.get("results", [])
        show = next(
            (
                item
                for item in results
                if isinstance(item, dict) and item.get("wrapperType") == "track"
            ),
            None,
        )
        if show is None and results:
            show = results[0]
        if not isinstance(show, dict):
            raise LookupError("未找到 Apple Podcasts 节目")
        self.cache.set(key, show, APPLE_TTL_SECONDS)
        return show

    def lookup_episodes(self, podcast_id: str, market: str) -> list[dict[str, Any]]:
        key = f"episodes:{market}:{podcast_id}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        payload = self._get_json(
            APPLE_LOOKUP_URL,
            params={
                "id": podcast_id,
                "country": market,
                "media": "podcast",
                "entity": "podcastEpisode",
                "limit": APPLE_EPISODE_LOOKUP_LIMIT,
            },
        )
        results = payload.get("results", [])
        episodes = [
            item
            for item in results
            if isinstance(item, dict)
            and item.get("wrapperType") == "podcastEpisode"
            and item.get("trackId") is not None
        ]
        if not episodes:
            raise LookupError("Apple Podcasts 未返回可匹配的单集")
        self.cache.set(key, episodes, APPLE_TTL_SECONDS)
        self.remember_episodes(episodes)
        return episodes

    def remember_episodes(self, results: list[dict[str, Any]]) -> None:
        for item in results:
            if not isinstance(item, dict) or item.get("trackId") is None:
                continue
            episode_url = item.get("episodeUrl")
            if isinstance(episode_url, str) and episode_url.startswith(("http://", "https://")):
                self.episode_cache.set(str(item["trackId"]), item, APPLE_TTL_SECONDS)

    def resolve_episode(
        self,
        podcast_id: str,
        episode_id: str,
        market: str = "cn",
    ) -> dict[str, Any]:
        cached = self.episode_cache.get(episode_id)
        if cached is not None and str(cached.get("collectionId")) == str(podcast_id):
            return cached
        episodes = self.lookup_episodes(podcast_id, market)
        match = next(
            (item for item in episodes if str(item.get("trackId")) == str(episode_id)),
            None,
        )
        if match is None:
            raise LookupError("未能在指定 Apple Podcasts 节目中匹配该单集")
        return match


class ApplePodcastsAdapter(PodcastSourceAdapter):
    source = "apple_podcasts"
    discover_modes = frozenset({"top"})

    def __init__(self, client: Optional[ApplePodcastsClient] = None):
        self.client = client or ApplePodcastsClient()

    @staticmethod
    def _genres(item: dict[str, Any]) -> list[str]:
        genres = item.get("genres")
        if isinstance(genres, list):
            return [
                str(value.get("name") if isinstance(value, dict) else value)
                for value in genres
                if value and (not isinstance(value, dict) or value.get("name"))
            ]
        primary = item.get("primaryGenreName")
        return [str(primary)] if primary else []

    @staticmethod
    def _cover(item: dict[str, Any]) -> str:
        for key in (
            "artworkUrl600",
            "artworkUrl512",
            "artworkUrl160",
            "artworkUrl100",
            "artworkUrl60",
        ):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value.replace("100x100", "600x600")
        return ""

    @classmethod
    def normalize_show(cls, item: dict[str, Any], market: str = "cn") -> PodcastCatalogItem:
        podcast_id = str(
            item.get("collectionId") or item.get("id") or item.get("trackId") or ""
        )
        title = str(
            item.get("collectionName")
            or item.get("trackName")
            or item.get("name")
            or "未命名节目"
        )
        url = str(
            item.get("collectionViewUrl")
            or item.get("trackViewUrl")
            or item.get("url")
            or ""
        )
        if not url and podcast_id:
            url = f"https://podcasts.apple.com/{market}/podcast/id{podcast_id}"
        return PodcastCatalogItem(
            source="apple_podcasts",
            kind="show",
            id=podcast_id,
            podcast_id=podcast_id,
            title=title,
            podcast_title=title,
            author=str(item.get("artistName") or ""),
            description=str(item.get("description") or ""),
            cover_url=cls._cover(item),
            genres=cls._genres(item),
            duration=0,
            published_at=item.get("releaseDate"),
            canonical_url=url,
        )

    @classmethod
    def normalize_episode(cls, item: dict[str, Any]) -> PodcastCatalogItem:
        episode_id = str(item.get("trackId") or item.get("id") or "")
        podcast_id = str(item.get("collectionId") or "")
        return PodcastCatalogItem(
            source="apple_podcasts",
            kind="episode",
            id=episode_id,
            podcast_id=podcast_id,
            title=str(item.get("trackName") or item.get("name") or "未命名单集"),
            podcast_title=str(item.get("collectionName") or ""),
            author=str(item.get("artistName") or ""),
            description=str(item.get("description") or item.get("shortDescription") or ""),
            cover_url=cls._cover(item),
            genres=cls._genres(item),
            duration=max(0, int(item.get("trackTimeMillis") or 0) // 1000),
            published_at=item.get("releaseDate"),
            canonical_url=str(item.get("trackViewUrl") or item.get("url") or ""),
            is_private=not bool(item.get("episodeUrl")),
        )

    def discover(
        self,
        mode: str,
        entity: str,
        market: str,
        cursor: Optional[Any],
        limit: int,
    ) -> PodcastCatalogPage:
        del cursor
        self.validate_mode(mode)
        results = self.client.top(entity, market, limit)
        return PodcastCatalogPage(
            items=(
                [self.normalize_show(item, market) for item in results]
                if entity == "show"
                else [self.normalize_episode(item) for item in results]
            )
        )

    def search(
        self,
        entity: str,
        query: str,
        market: str,
        cursor: Optional[Any],
        limit: int,
    ) -> PodcastCatalogPage:
        del cursor
        results = self.client.search(entity, query, market, limit)
        if entity == "show":
            items = [self.normalize_show(item, market) for item in results]
        else:
            items = [self.normalize_episode(item) for item in results]
        return PodcastCatalogPage(items=items)

    def get_show(self, podcast_id: str, market: str) -> PodcastCatalogItem:
        return self.normalize_show(self.client.lookup_show(podcast_id, market), market)

    def list_episodes(
        self,
        podcast_id: str,
        market: str,
        cursor: Optional[Any],
        limit: int,
    ) -> PodcastCatalogPage:
        episodes = self.client.lookup_episodes(podcast_id, market)
        try:
            offset = max(0, int(cursor or 0))
        except (TypeError, ValueError):
            offset = 0
        selected = episodes[offset : offset + limit]
        next_cursor = offset + len(selected) if offset + len(selected) < len(episodes) else None
        return PodcastCatalogPage(
            items=[self.normalize_episode(item) for item in selected],
            cursor=next_cursor,
            total=len(episodes),
        )


apple_podcasts_client = ApplePodcastsClient()
