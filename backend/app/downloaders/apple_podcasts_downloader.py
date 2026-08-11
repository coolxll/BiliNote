from typing import Optional, Union

from app.downloaders.base import Downloader
from app.enmus.note_enums import DownloadQuality
from app.models.audio_model import AudioDownloadResult
from app.providers.apple_podcasts import ApplePodcastsProvider
from app.utils.path_helper import get_data_dir


class ApplePodcastsDownloader(Downloader):
    def __init__(self):
        super().__init__()
        self.provider = ApplePodcastsProvider()

    def download(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
        quality: DownloadQuality = "fast",
        need_video: Optional[bool] = False,
        skip_download: bool = False,
    ) -> AudioDownloadResult:
        del quality, need_video
        episode = self.provider.resolve(video_url)
        target_dir = output_dir or get_data_dir() or self.cache_data
        if not target_dir:
            raise RuntimeError("未配置音频输出目录")
        audio_path = (
            self.provider.audio_path(episode, target_dir)
            if skip_download
            else self.provider.download_audio(episode, target_dir)
        )
        return AudioDownloadResult(
            file_path=audio_path,
            title=episode.title,
            duration=episode.duration,
            cover_url=episode.cover_url,
            platform="apple_podcasts",
            video_id=episode.episode_id,
            raw_info=episode.raw_info,
            video_path=None,
        )

    def download_video(self, video_url: str, output_dir: Union[str, None] = None) -> str:
        del video_url, output_dir
        raise RuntimeError("Apple Podcasts 仅支持音频笔记，不支持视频下载或截图")
