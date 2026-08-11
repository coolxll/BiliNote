from pydantic import AnyUrl, validator, BaseModel, field_validator
import re
from urllib.parse import parse_qs, urlparse

SUPPORTED_PLATFORMS = {
    "bilibili": r"(https?://)?(www\.)?bilibili\.com/video/[a-zA-Z0-9]+",
    "youtube": r"(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[\w\-]+",
    "xiaoyuzhou": r"https?://(www\.)?xiaoyuzhoufm\.com/episode/[0-9a-fA-F]{24}(?:[/?#].*)?$",
    "apple_podcasts": "apple_podcasts",
    "douyin": "douyin",
    "kuaishou": "kuaishou"
}


def _is_apple_episode_url(url: str) -> bool:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    episode_ids = parse_qs(parsed.query, keep_blank_values=True).get("i", [])
    return bool(
        parsed.scheme == "https"
        and parsed.netloc == "podcasts.apple.com"
        and len(parts) == 4
        and parts[0].lower() in {"cn", "us"}
        and parts[1] == "podcast"
        and parts[-1].startswith("id")
        and parts[-1][2:].isdigit()
        and len(episode_ids) == 1
        and episode_ids[0].isdigit()
    )


def is_supported_video_url(url: str) -> bool:
    parsed = urlparse(url)

    # 检查是否为Bilibili的短链接
    if parsed.netloc == "b23.tv":
        return True

    for name, pattern in SUPPORTED_PLATFORMS.items():
        if pattern == "apple_podcasts":
            if _is_apple_episode_url(url):
                return True
        elif pattern in ["douyin", "kuaishou"]:
            if pattern in url:
                return True
        else:
            if re.match(pattern, url):
                return True
    return False


class VideoRequest(BaseModel):
    url: AnyUrl
    platform: str

    @field_validator("url")
    def validate_video_url(cls, v):
        if not is_supported_video_url(str(v)):
            raise ValueError("暂不支持该视频平台或链接格式无效")
        return v
