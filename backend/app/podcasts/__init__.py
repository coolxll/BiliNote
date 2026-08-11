from app.podcasts.apple import ApplePodcastsAdapter, apple_podcasts_client
from app.podcasts.base import PodcastSourceAdapter
from app.podcasts.models import PodcastCatalogItem, PodcastCatalogPage
from app.podcasts.xiaoyuzhou import XiaoyuzhouPodcastAdapter


ADAPTERS: dict[str, PodcastSourceAdapter] = {
    "apple_podcasts": ApplePodcastsAdapter(apple_podcasts_client),
    "xiaoyuzhou": XiaoyuzhouPodcastAdapter(),
}


def get_podcast_adapter(source: str) -> PodcastSourceAdapter:
    try:
        return ADAPTERS[source]
    except KeyError as exc:
        raise ValueError(f"不支持的 Podcast 来源: {source}") from exc


__all__ = [
    "ADAPTERS",
    "PodcastCatalogItem",
    "PodcastCatalogPage",
    "PodcastSourceAdapter",
    "apple_podcasts_client",
    "get_podcast_adapter",
]
