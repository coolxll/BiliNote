from app.downloaders.bilibili_downloader import BilibiliDownloader
from app.downloaders.apple_podcasts_downloader import ApplePodcastsDownloader
from app.downloaders.douyin_downloader import DouyinDownloader
from app.downloaders.kuaishou_downloader import KuaiShouDownloader
from app.downloaders.local_downloader import LocalDownloader
from app.downloaders.youtube_downloader import YoutubeDownloader
from app.downloaders.xiaoyuzhou_downloader import XiaoyuzhouDownloader

SUPPORT_PLATFORM_MAP = {
    'youtube':YoutubeDownloader(),
    'bilibili':BilibiliDownloader(),
    'tiktok':DouyinDownloader(),
    'kuaishou':KuaiShouDownloader(),
    'douyin':DouyinDownloader(),
    'xiaoyuzhou':XiaoyuzhouDownloader(),
    'apple_podcasts':ApplePodcastsDownloader(),
    'local':LocalDownloader()
}
