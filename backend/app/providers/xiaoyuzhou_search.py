from typing import Any, Dict, Optional

from app.providers.xiaoyuzhou_auth import (
    API_BASE_URL,
    XiaoyuzhouAuthProvider,
)


class XiaoyuzhouSearchProvider:
    """Isolated Xiaoyuzhou episode search provider."""

    def __init__(self, auth_provider: Optional[XiaoyuzhouAuthProvider] = None):
        self.auth = auth_provider or XiaoyuzhouAuthProvider()

    def search_episodes(
        self,
        keyword: str,
        load_more_key: Optional[Dict[str, Any]] = None,
        pid: Optional[str] = None,
    ) -> Dict[str, Any]:
        keyword = keyword.strip()
        if not keyword:
            raise ValueError("搜索关键词不能为空")

        payload: Dict[str, Any] = {
            "limit": "20",
            "sourcePageName": "4",
            "type": "EPISODE",
            "currentPageName": "4",
            "keyword": keyword,
        }
        if load_more_key:
            payload["loadMoreKey"] = load_more_key
        if pid:
            payload["pid"] = pid

        access_token = self.auth.access_token()
        response = self._request(payload, access_token)
        if response.status_code == 401:
            access_token = self.auth.refresh_tokens()
            response = self._request(payload, access_token)
        self.auth.raise_for_response(response, "搜索小宇宙单集失败")

        result = self.auth.response_json(response)
        raw_items = result.get("data", [])
        items = [
            self._normalize_episode(item)
            for item in raw_items
            if isinstance(item, dict) and item.get("type") == "EPISODE" and item.get("eid")
        ]
        return {
            "items": items,
            "load_more_key": result.get("loadMoreKey"),
        }

    def _request(self, payload: Dict[str, Any], access_token: str):
        return self.auth.session.post(
            f"{API_BASE_URL}/v1/search/create",
            json=payload,
            headers=self.auth.headers(access_token=access_token),
            timeout=30,
        )

    @staticmethod
    def _image_url(owner: Dict[str, Any]) -> str:
        image = owner.get("image") if isinstance(owner, dict) else None
        if not isinstance(image, dict):
            return ""
        for key in ("middlePicUrl", "picUrl", "largePicUrl", "smallPicUrl", "thumbnailUrl"):
            value = image.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    @classmethod
    def _normalize_episode(cls, episode: Dict[str, Any]) -> Dict[str, Any]:
        podcast = episode.get("podcast") if isinstance(episode.get("podcast"), dict) else {}
        cover_url = cls._image_url(episode) or cls._image_url(podcast)
        eid = str(episode.get("eid", ""))
        return {
            "eid": eid,
            "pid": str(episode.get("pid") or podcast.get("pid") or ""),
            "title": str(episode.get("title") or "未命名单集"),
            "podcast_title": str(podcast.get("title") or ""),
            "duration": int(episode.get("duration") or 0),
            "pub_date": str(episode.get("pubDate") or ""),
            "cover_url": cover_url,
            "description": str(episode.get("description") or ""),
            "is_private": bool(episode.get("isPrivateMedia", False)),
            "episode_url": f"https://www.xiaoyuzhoufm.com/episode/{eid}",
        }
