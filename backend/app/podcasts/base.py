from abc import ABC, abstractmethod
from typing import Any, Optional

from app.podcasts.models import PodcastCatalogItem, PodcastCatalogPage


class PodcastSourceAdapter(ABC):
    source: str
    discover_modes: frozenset[str]

    def validate_mode(self, mode: str) -> None:
        if mode not in self.discover_modes:
            modes = ", ".join(sorted(self.discover_modes))
            raise ValueError(f"{self.source} 不支持发现模式 {mode}，可用模式: {modes}")

    @abstractmethod
    def discover(
        self,
        mode: str,
        entity: str,
        market: str,
        cursor: Optional[Any],
        limit: int,
    ) -> PodcastCatalogPage:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        entity: str,
        query: str,
        market: str,
        cursor: Optional[Any],
        limit: int,
    ) -> PodcastCatalogPage:
        raise NotImplementedError

    @abstractmethod
    def get_show(self, podcast_id: str, market: str) -> PodcastCatalogItem:
        raise NotImplementedError

    @abstractmethod
    def list_episodes(
        self,
        podcast_id: str,
        market: str,
        cursor: Optional[Any],
        limit: int,
    ) -> PodcastCatalogPage:
        raise NotImplementedError
