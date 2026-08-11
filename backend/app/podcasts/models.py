from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


PodcastSource = Literal["apple_podcasts", "xiaoyuzhou"]
PodcastItemKind = Literal["show", "episode"]


class PodcastCatalogItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: PodcastSource
    kind: PodcastItemKind
    id: str
    podcast_id: str
    title: str
    podcast_title: str = ""
    author: str = ""
    description: str = ""
    cover_url: str = ""
    genres: list[str] = Field(default_factory=list)
    duration: int = 0
    published_at: Optional[str] = None
    canonical_url: str
    is_private: bool = False


class PodcastCatalogPage(BaseModel):
    items: list[PodcastCatalogItem] = Field(default_factory=list)
    cursor: Optional[Any] = None
    total: Optional[int] = None
