import json
from typing import Any, Iterable, Optional

from app.podcasts.base import PodcastSourceAdapter
from app.podcasts.cache import BoundedTTLCache
from app.podcasts.models import PodcastCatalogItem, PodcastCatalogPage
from app.providers.xiaoyuzhou_auth import API_BASE_URL, XiaoyuzhouAuthProvider


XIAOYUZHOU_TTL_SECONDS = 2 * 60
TOP_LIST_CATEGORIES = {
    "hot": "HOT_EPISODES_IN_24_HOURS",
    "rising": "SKYROCKET_EPISODES",
    "new": "NEW_STAR_EPISODES",
}


class XiaoyuzhouPodcastAdapter(PodcastSourceAdapter):
    source = "xiaoyuzhou"
    discover_modes = frozenset({"personalized", "hot", "rising", "new"})

    def __init__(self, auth_provider: Optional[XiaoyuzhouAuthProvider] = None):
        self.auth = auth_provider or XiaoyuzhouAuthProvider()
        self.cache: BoundedTTLCache[Any] = BoundedTTLCache(max_entries=256)

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        token = self.auth.access_token()
        response = self.auth.session.request(
            method,
            f"{API_BASE_URL}{path}",
            headers=self.auth.headers(access_token=token),
            timeout=(10, 30),
            **kwargs,
        )
        if response.status_code == 401:
            token = self.auth.refresh_tokens()
            response = self.auth.session.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=self.auth.headers(access_token=token),
                timeout=(10, 30),
                **kwargs,
            )
        self.auth.raise_for_response(response, "读取小宇宙 Podcast 数据失败")
        payload = self.auth.response_json(response)
        if not payload:
            raise RuntimeError("小宇宙返回了空数据")
        return payload

    @staticmethod
    def _image_url(owner: dict[str, Any]) -> str:
        image = owner.get("image") if isinstance(owner, dict) else None
        candidates: list[Any]
        if isinstance(image, dict):
            candidates = [image]
        elif isinstance(image, list):
            candidates = [item for item in image if isinstance(item, dict)]
        else:
            candidates = []
        for candidate in candidates:
            for key in (
                "largePicUrl",
                "picUrl",
                "middlePicUrl",
                "smallPicUrl",
                "thumbnailUrl",
            ):
                value = candidate.get(key)
                if isinstance(value, str) and value:
                    return value
        return ""

    @staticmethod
    def _genres(item: dict[str, Any]) -> list[str]:
        labels = item.get("topicLabels") or item.get("labels") or []
        return [
            str(label.get("name") or label.get("title"))
            for label in labels
            if isinstance(label, dict) and (label.get("name") or label.get("title"))
        ]

    @classmethod
    def normalize_show(cls, item: dict[str, Any]) -> PodcastCatalogItem:
        podcast_id = str(item.get("pid") or "")
        title = str(item.get("title") or "未命名节目")
        author = item.get("author")
        if isinstance(author, dict):
            author = author.get("nickname") or author.get("name") or ""
        return PodcastCatalogItem(
            source="xiaoyuzhou",
            kind="show",
            id=podcast_id,
            podcast_id=podcast_id,
            title=title,
            podcast_title=title,
            author=str(author or ""),
            description=str(item.get("description") or item.get("brief") or ""),
            cover_url=cls._image_url(item),
            genres=cls._genres(item),
            duration=0,
            published_at=item.get("latestEpisodePubDate"),
            canonical_url=f"https://www.xiaoyuzhoufm.com/podcast/{podcast_id}",
        )

    @classmethod
    def normalize_episode(cls, item: dict[str, Any]) -> PodcastCatalogItem:
        podcast = item.get("podcast") if isinstance(item.get("podcast"), dict) else {}
        episode_id = str(item.get("eid") or "")
        podcast_id = str(item.get("pid") or podcast.get("pid") or "")
        author = podcast.get("author")
        if isinstance(author, dict):
            author = author.get("nickname") or author.get("name") or ""
        return PodcastCatalogItem(
            source="xiaoyuzhou",
            kind="episode",
            id=episode_id,
            podcast_id=podcast_id,
            title=str(item.get("title") or "未命名单集"),
            podcast_title=str(podcast.get("title") or ""),
            author=str(author or ""),
            description=str(item.get("description") or item.get("shownotes") or ""),
            cover_url=cls._image_url(item) or cls._image_url(podcast),
            genres=cls._genres(item) or cls._genres(podcast),
            duration=max(0, int(item.get("duration") or 0)),
            published_at=item.get("pubDate"),
            canonical_url=f"https://www.xiaoyuzhoufm.com/episode/{episode_id}",
            is_private=bool(item.get("isPrivateMedia", False)),
        )

    @staticmethod
    def _walk_episodes(value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, dict):
            if value.get("eid"):
                yield value
                return
            for child in value.values():
                yield from XiaoyuzhouPodcastAdapter._walk_episodes(child)
        elif isinstance(value, list):
            for child in value:
                yield from XiaoyuzhouPodcastAdapter._walk_episodes(child)

    @classmethod
    def _dedupe_episodes(cls, value: Any, limit: int) -> list[PodcastCatalogItem]:
        seen: set[str] = set()
        items: list[PodcastCatalogItem] = []
        for raw in cls._walk_episodes(value):
            episode_id = str(raw.get("eid") or "")
            if not episode_id or episode_id in seen:
                continue
            seen.add(episode_id)
            items.append(cls.normalize_episode(raw))
            if len(items) >= limit:
                break
        return items

    @classmethod
    def _dedupe_shows_from_episodes(
        cls,
        value: Any,
        limit: int,
    ) -> list[PodcastCatalogItem]:
        seen: set[str] = set()
        items: list[PodcastCatalogItem] = []
        for episode in cls._walk_episodes(value):
            podcast = episode.get("podcast")
            if not isinstance(podcast, dict):
                continue
            podcast_id = str(podcast.get("pid") or "")
            if not podcast_id or podcast_id in seen:
                continue
            seen.add(podcast_id)
            items.append(cls.normalize_show(podcast))
            if len(items) >= limit:
                break
        return items

    def discover(
        self,
        mode: str,
        entity: str,
        market: str,
        cursor: Optional[Any],
        limit: int,
    ) -> PodcastCatalogPage:
        del market
        self.validate_mode(mode)
        if entity not in {"show", "episode"}:
            raise ValueError(f"小宇宙不支持实体类型: {entity}")
        cursor_key = (
            json.dumps(cursor, sort_keys=True, ensure_ascii=False) if cursor is not None else ""
        )
        key = f"discover:{mode}:{entity}:{cursor_key}:{limit}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if mode == "personalized":
            body: dict[str, Any] = {"returnAll": "false"}
            if cursor is not None:
                body["loadMoreKey"] = cursor
            payload = self._request("post", "/v1/discovery-feed/list", json=body)
            raw_items = payload.get("data", [])
            page = PodcastCatalogPage(
                items=(
                    self._dedupe_episodes(raw_items, limit)
                    if entity == "episode"
                    else self._dedupe_shows_from_episodes(raw_items, limit)
                ),
                cursor=payload.get("loadMoreKey"),
            )
        else:
            payload = self._request(
                "get",
                "/v1/top-list/get",
                params={"category": TOP_LIST_CATEGORIES[mode]},
            )
            raw_items = payload.get("data", {}).get("items", [])
            page = PodcastCatalogPage(items=(
                self._dedupe_episodes(raw_items, limit)
                if entity == "episode"
                else self._dedupe_shows_from_episodes(raw_items, limit)
            ))
        if page.items:
            self.cache.set(key, page, XIAOYUZHOU_TTL_SECONDS)
        return page

    def search(
        self,
        entity: str,
        query: str,
        market: str,
        cursor: Optional[Any],
        limit: int,
    ) -> PodcastCatalogPage:
        del market
        cursor_key = (
            json.dumps(cursor, sort_keys=True, ensure_ascii=False) if cursor is not None else ""
        )
        key = f"search:{entity}:{cursor_key}:{limit}:{query}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        body: dict[str, Any] = {
            "limit": str(limit),
            "sourcePageName": "4",
            "type": "PODCAST" if entity == "show" else "EPISODE",
            "currentPageName": "4",
            "keyword": query,
        }
        if cursor is not None:
            body["loadMoreKey"] = cursor
        payload = self._request("post", "/v1/search/create", json=body)
        raw_items = payload.get("data", [])
        if entity == "show":
            items = [
                self.normalize_show(item)
                for item in raw_items
                if isinstance(item, dict) and item.get("pid")
            ][:limit]
        else:
            items = self._dedupe_episodes(raw_items, limit)
        page = PodcastCatalogPage(items=items, cursor=payload.get("loadMoreKey"))
        if items:
            self.cache.set(key, page, XIAOYUZHOU_TTL_SECONDS)
        return page

    def get_show(self, podcast_id: str, market: str) -> PodcastCatalogItem:
        del market
        key = f"show:{podcast_id}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        payload = self._request("get", "/v1/podcast/get", params={"pid": podcast_id})
        raw = payload.get("data")
        if not isinstance(raw, dict) or not raw.get("pid"):
            raise LookupError("未找到小宇宙节目")
        show = self.normalize_show(raw)
        self.cache.set(key, show, XIAOYUZHOU_TTL_SECONDS)
        return show

    def list_episodes(
        self,
        podcast_id: str,
        market: str,
        cursor: Optional[Any],
        limit: int,
    ) -> PodcastCatalogPage:
        del market
        cursor_key = (
            json.dumps(cursor, sort_keys=True, ensure_ascii=False) if cursor is not None else ""
        )
        key = f"episodes:{podcast_id}:{cursor_key}:{limit}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        body: dict[str, Any] = {"pid": podcast_id, "limit": str(limit), "order": "desc"}
        if cursor is not None:
            body["loadMoreKey"] = cursor
        payload = self._request("post", "/v1/episode/list", json=body)
        page = PodcastCatalogPage(
            items=self._dedupe_episodes(payload.get("data", []), limit),
            cursor=payload.get("loadMoreKey") or payload.get("loadNextKey"),
            total=payload.get("total"),
        )
        if page.items:
            self.cache.set(key, page, XIAOYUZHOU_TTL_SECONDS)
        return page
