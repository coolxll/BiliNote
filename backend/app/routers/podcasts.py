import logging
import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.podcasts import get_podcast_adapter
from app.providers.xiaoyuzhou_auth import (
    XiaoyuzhouApiError,
    XiaoyuzhouAuthenticationRequired,
)
from app.utils.response import ResponseWrapper as R


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/podcasts", tags=["podcasts"])


class DiscoverRequest(BaseModel):
    source: Literal["apple_podcasts", "xiaoyuzhou"]
    mode: str = Field(min_length=1, max_length=32)
    entity: Optional[Literal["show", "episode"]] = None
    market: Literal["cn", "us"] = "cn"
    cursor: Optional[Any] = None
    limit: int = Field(default=20, ge=1, le=30)


class SearchRequest(BaseModel):
    source: Literal["apple_podcasts", "xiaoyuzhou"]
    entity: Literal["show", "episode"]
    query: str = Field(min_length=1, max_length=100)
    market: Literal["cn", "us"] = "cn"
    cursor: Optional[Any] = None
    limit: int = Field(default=20, ge=1, le=30)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("搜索关键词不能为空")
        return value


class EpisodeListRequest(BaseModel):
    market: Literal["cn", "us"] = "cn"
    cursor: Optional[Any] = None
    limit: int = Field(default=20, ge=1, le=30)


def _provider_error(error: Exception):
    if isinstance(error, XiaoyuzhouAuthenticationRequired):
        return R.error(
            msg=str(error),
            code=401,
            data={"reason": "xiaoyuzhou_login_required"},
        )
    if isinstance(error, XiaoyuzhouApiError):
        return R.error(msg=str(error), code=error.status_code)
    if isinstance(error, (LookupError, ValueError)):
        raise HTTPException(status_code=422, detail=str(error))
    raise HTTPException(status_code=502, detail="Podcast 来源暂时不可用")


def _run(source: str, operation: str, callback):
    started = time.perf_counter()
    result_count = 0
    status_code = 0
    try:
        result = callback(get_podcast_adapter(source))
        result_count = len(getattr(result, "items", []) or [])
        return R.success(data=result.model_dump(mode="json"))
    except Exception as error:
        status_code = getattr(error, "status_code", 500)
        return _provider_error(error)
    finally:
        logger.info(
            "podcast source=%s operation=%s results=%s elapsed_ms=%s status=%s",
            source,
            operation,
            result_count,
            int((time.perf_counter() - started) * 1000),
            status_code,
        )


@router.post("/discover")
def discover(data: DiscoverRequest):
    entity = data.entity or ("show" if data.source == "apple_podcasts" else "episode")
    return _run(
        data.source,
        f"discover:{data.mode}:{entity}",
        lambda adapter: adapter.discover(
            data.mode,
            entity,
            data.market,
            data.cursor,
            data.limit,
        ),
    )


@router.post("/search")
def search(data: SearchRequest):
    return _run(
        data.source,
        f"search:{data.entity}",
        lambda adapter: adapter.search(data.entity, data.query, data.market, data.cursor, data.limit),
    )


@router.get("/{source}/shows/{podcast_id}")
def get_show(
    source: Literal["apple_podcasts", "xiaoyuzhou"],
    podcast_id: str,
    market: Literal["cn", "us"] = Query(default="cn"),
):
    return _run(
        source,
        "show",
        lambda adapter: _ShowResult(adapter.get_show(podcast_id, market)),
    )


class _ShowResult:
    def __init__(self, show):
        self.show = show
        self.items = []

    def model_dump(self, mode="json"):
        return self.show.model_dump(mode=mode)


@router.post("/{source}/shows/{podcast_id}/episodes")
def list_episodes(
    source: Literal["apple_podcasts", "xiaoyuzhou"],
    podcast_id: str,
    data: EpisodeListRequest,
):
    return _run(
        source,
        "episodes",
        lambda adapter: adapter.list_episodes(podcast_id, data.market, data.cursor, data.limit),
    )
