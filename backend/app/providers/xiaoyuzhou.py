import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EPISODE_ID_PATTERN = re.compile(r"[0-9a-fA-F]{24}")
XIAOYUZHOU_HOSTS = {"xiaoyuzhoufm.com", "www.xiaoyuzhoufm.com"}

PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.xiaoyuzhoufm.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class XiaoyuzhouEpisode:
    episode_id: str
    title: str
    duration: float
    audio_url: str
    audio_extension: str
    cover_url: Optional[str]
    raw_info: dict


class XiaoyuzhouProvider:
    """Resolve and download public Xiaoyuzhou episode audio."""

    def resolve(self, episode_url: str) -> XiaoyuzhouEpisode:
        episode_id = self.extract_episode_id(episode_url)
        if not episode_id:
            raise ValueError("无效的小宇宙单集链接，请使用 /episode/<id> 格式")

        response = requests.get(episode_url, headers=PAGE_HEADERS, timeout=30)
        response.raise_for_status()
        episode = self.parse_episode_page(response.text)
        audio_url = self.extract_audio_url(episode)
        if not audio_url:
            if episode.get("isPrivateMedia"):
                raise RuntimeError("该小宇宙单集为付费或私有内容，无法下载公开音频")
            raise RuntimeError("未能从小宇宙页面提取公开音频地址")
        parsed_audio_url = urlparse(audio_url)
        if parsed_audio_url.scheme not in {"http", "https"} or not parsed_audio_url.netloc:
            raise RuntimeError("小宇宙页面返回了无效的音频地址")

        candidate_id = episode.get("eid") or episode.get("id")
        resolved_id = (
            candidate_id
            if isinstance(candidate_id, str) and EPISODE_ID_PATTERN.fullmatch(candidate_id)
            else episode_id
        )
        podcast = episode.get("podcast") if isinstance(episode.get("podcast"), dict) else {}
        labels = episode.get("labels") if isinstance(episode.get("labels"), list) else []
        tags = [item.get("name") for item in labels if isinstance(item, dict) and item.get("name")]
        raw_info = dict(episode)
        raw_info.update({"source_url": episode_url, "audio_url": audio_url, "tags": tags})

        return XiaoyuzhouEpisode(
            episode_id=resolved_id,
            title=episode.get("title") or f"小宇宙单集 {resolved_id}",
            duration=float(episode.get("duration") or 0),
            audio_url=audio_url,
            audio_extension=self.audio_extension(audio_url, episode),
            cover_url=self.extract_cover_url(episode, podcast),
            raw_info=raw_info,
        )

    def download_audio(self, episode: XiaoyuzhouEpisode, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        audio_path = self.audio_path(episode, output_dir)
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            logger.info("复用已下载的小宇宙音频: %s", audio_path)
            return audio_path

        temp_path = f"{audio_path}.part"
        try:
            response = requests.get(
                episode.audio_url,
                headers={**PAGE_HEADERS, "Accept": "audio/*,*/*;q=0.8"},
                stream=True,
                timeout=(15, 120),
            )
            response.raise_for_status()
            with open(temp_path, "wb") as audio_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        audio_file.write(chunk)
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                raise RuntimeError("小宇宙音频下载结果为空")
            os.replace(temp_path, audio_path)
            return audio_path
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    @staticmethod
    def audio_path(episode: XiaoyuzhouEpisode, output_dir: str) -> str:
        return os.path.join(output_dir, f"{episode.episode_id}{episode.audio_extension}")

    @staticmethod
    def extract_episode_id(url: str) -> Optional[str]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in XIAOYUZHOU_HOSTS:
            return None
        match = re.fullmatch(r"/episode/([0-9a-fA-F]{24})/?", parsed.path)
        return match.group(1) if match else None

    @staticmethod
    def parse_episode_page(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data and next_data.string:
            try:
                payload = json.loads(next_data.string)
            except json.JSONDecodeError as exc:
                raise RuntimeError("小宇宙页面数据格式无效") from exc

            page_props = payload.get("props", {}).get("pageProps", {})
            episode = page_props.get("episode")
            if isinstance(episode, dict):
                return episode

            dehydrated_state = page_props.get("dehydratedState", {})
            for query in dehydrated_state.get("queries", []):
                if not isinstance(query, dict):
                    continue
                data = query.get("state", {}).get("data", {})
                episode = data.get("episode") if isinstance(data, dict) else None
                if isinstance(episode, dict):
                    return episode

        og_audio = soup.find("meta", attrs={"property": "og:audio"})
        if og_audio and og_audio.get("content"):
            og_title = soup.find("meta", attrs={"property": "og:title"})
            return {
                "title": og_title.get("content") if og_title else None,
                "enclosure": {"url": og_audio.get("content")},
            }

        raise RuntimeError("未能从小宇宙页面找到单集数据")

    @staticmethod
    def extract_audio_url(episode: dict) -> Optional[str]:
        enclosure = episode.get("enclosure")
        if isinstance(enclosure, dict) and enclosure.get("url"):
            return enclosure["url"]

        media = episode.get("media")
        if isinstance(media, dict):
            source = media.get("source")
            if isinstance(source, dict) and source.get("url"):
                return source["url"]
        return None

    @staticmethod
    def extract_cover_url(episode: dict, podcast: dict) -> Optional[str]:
        for owner in (episode, podcast):
            image = owner.get("image") if isinstance(owner, dict) else None
            if isinstance(image, dict):
                for key in ("largePicUrl", "picUrl", "middlePicUrl", "thumbnailUrl"):
                    if image.get(key):
                        return image[key]
        return None

    @staticmethod
    def audio_extension(audio_url: str, episode: dict) -> str:
        suffix = Path(urlparse(audio_url).path).suffix.lower()
        if suffix in {".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac"}:
            return suffix

        media = episode.get("media")
        mime_type = media.get("mimeType") if isinstance(media, dict) else None
        return {
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/aac": ".aac",
            "audio/ogg": ".ogg",
            "audio/wav": ".wav",
            "audio/flac": ".flac",
        }.get(mime_type, ".m4a")
