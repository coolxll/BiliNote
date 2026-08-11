import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests

from app.podcasts.apple import ApplePodcastsClient, apple_podcasts_client


logger = logging.getLogger(__name__)
APPLE_PODCAST_HOST = "podcasts.apple.com"


def parse_apple_episode_url(url: str) -> Optional[tuple[str, str, str]]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != APPLE_PODCAST_HOST:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4 or parts[1] != "podcast" or not parts[-1].startswith("id"):
        return None
    market = parts[0].lower()
    if market not in {"cn", "us"}:
        return None
    podcast_id = parts[-1][2:]
    episode_ids = parse_qs(parsed.query, keep_blank_values=True).get("i", [])
    if not podcast_id.isdigit() or len(episode_ids) != 1 or not episode_ids[0].isdigit():
        return None
    return podcast_id, episode_ids[0], market


@dataclass(frozen=True)
class ApplePodcastEpisode:
    podcast_id: str
    episode_id: str
    market: str
    title: str
    duration: float
    audio_url: str
    audio_extension: str
    cover_url: Optional[str]
    canonical_url: str
    raw_info: dict[str, Any]


class ApplePodcastsProvider:
    def __init__(self, client: Optional[ApplePodcastsClient] = None):
        self.client = client or apple_podcasts_client

    def resolve(self, episode_url: str) -> ApplePodcastEpisode:
        parsed = parse_apple_episode_url(episode_url)
        if parsed is None:
            raise ValueError("无效的 Apple Podcasts 单集链接，链接必须包含 ?i=<单集 ID>")
        podcast_id, episode_id, market = parsed
        item = self.client.resolve_episode(podcast_id, episode_id, market)
        audio_url = item.get("episodeUrl")
        if not isinstance(audio_url, str) or not audio_url.startswith(("http://", "https://")):
            raise RuntimeError("该 Apple Podcasts 单集没有可下载的公开音频")
        canonical_url = item.get("trackViewUrl")
        if not isinstance(canonical_url, str) or not canonical_url:
            canonical_url = episode_url
        raw_info = {
            "collection_id": podcast_id,
            "collection_name": str(item.get("collectionName") or ""),
            "release_date": item.get("releaseDate"),
            "source_url": canonical_url,
        }
        return ApplePodcastEpisode(
            podcast_id=podcast_id,
            episode_id=episode_id,
            market=market,
            title=str(item.get("trackName") or f"Apple Podcasts 单集 {episode_id}"),
            duration=max(0, int(item.get("trackTimeMillis") or 0) / 1000),
            audio_url=audio_url,
            audio_extension=self.audio_extension(audio_url, item),
            cover_url=self.cover_url(item),
            canonical_url=canonical_url,
            raw_info=raw_info,
        )

    def download_audio(self, episode: ApplePodcastEpisode, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        audio_path = self.audio_path(episode, output_dir)
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            logger.info("复用已下载的 Apple Podcasts 音频: %s", audio_path)
            return audio_path
        temp_path = f"{audio_path}.part"
        try:
            response = requests.get(
                episode.audio_url,
                headers={"Accept": "audio/*,*/*;q=0.8", "User-Agent": "BiliNote/1.0"},
                stream=True,
                timeout=(15, 120),
            )
            response.raise_for_status()
            with open(temp_path, "wb") as audio_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        audio_file.write(chunk)
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                raise RuntimeError("Apple Podcasts 音频下载结果为空")
            os.replace(temp_path, audio_path)
            return audio_path
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    @staticmethod
    def audio_path(episode: ApplePodcastEpisode, output_dir: str) -> str:
        return os.path.join(output_dir, f"{episode.episode_id}{episode.audio_extension}")

    @staticmethod
    def audio_extension(audio_url: str, item: dict[str, Any]) -> str:
        suffix = Path(urlparse(audio_url).path).suffix.lower()
        if suffix in {".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac"}:
            return suffix
        extension = str(item.get("episodeFileExtension") or "").lower()
        return f".{extension}" if extension in {"mp3", "m4a", "aac", "ogg", "wav", "flac"} else ".mp3"

    @staticmethod
    def cover_url(item: dict[str, Any]) -> Optional[str]:
        for key in ("artworkUrl600", "artworkUrl160", "artworkUrl100", "artworkUrl60"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value.replace("100x100", "600x600")
        return None
