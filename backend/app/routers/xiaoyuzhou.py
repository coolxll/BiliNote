from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.providers.xiaoyuzhou_auth import (
    XiaoyuzhouApiError,
    XiaoyuzhouAuthenticationRequired,
    XiaoyuzhouAuthProvider,
)
from app.providers.xiaoyuzhou_search import XiaoyuzhouSearchProvider
from app.utils.response import ResponseWrapper as R


router = APIRouter()
auth_provider = XiaoyuzhouAuthProvider()
search_provider = XiaoyuzhouSearchProvider(auth_provider)


class PhoneRequest(BaseModel):
    mobile_phone_number: str = Field(min_length=5, max_length=24)
    area_code: str = Field(default="+86", min_length=2, max_length=8)

    @field_validator("mobile_phone_number", "area_code")
    @classmethod
    def strip_value(cls, value: str) -> str:
        return value.strip()


class LoginRequest(PhoneRequest):
    verify_code: str = Field(min_length=4, max_length=8)

    @field_validator("verify_code")
    @classmethod
    def strip_code(cls, value: str) -> str:
        return value.strip()


class QrPollRequest(BaseModel):
    id: str = Field(min_length=8, max_length=128)

    @field_validator("id")
    @classmethod
    def strip_id(cls, value: str) -> str:
        return value.strip()


class SearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=100)
    load_more_key: Optional[Dict[str, Any]] = None
    pid: Optional[str] = Field(default=None, max_length=64)

    @field_validator("keyword")
    @classmethod
    def strip_keyword(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("搜索关键词不能为空")
        return value


def provider_error(error: Exception):
    if isinstance(error, XiaoyuzhouAuthenticationRequired):
        return R.error(msg=str(error), code=401, data={"reason": "xiaoyuzhou_login_required"})
    if isinstance(error, XiaoyuzhouApiError):
        return R.error(msg=str(error), code=error.status_code)
    return R.error(msg=str(error), code=500)


@router.get("/xiaoyuzhou/auth/status")
def auth_status():
    return R.success(data=auth_provider.auth_status())


@router.post("/xiaoyuzhou/auth/send-code")
def send_code(data: PhoneRequest):
    try:
        result = auth_provider.send_code(data.mobile_phone_number, data.area_code)
        return R.success(data=result, msg=result["message"])
    except Exception as error:
        return provider_error(error)


@router.post("/xiaoyuzhou/auth/qrcode/create")
def create_qrcode():
    try:
        return R.success(data=auth_provider.create_qr_session())
    except Exception as error:
        return provider_error(error)


@router.post("/xiaoyuzhou/auth/qrcode/poll")
def poll_qrcode(data: QrPollRequest):
    try:
        result = auth_provider.poll_qr_session(data.id)
        return R.success(data=result)
    except Exception as error:
        return provider_error(error)


@router.post("/xiaoyuzhou/auth/login")
def login(data: LoginRequest):
    try:
        status = auth_provider.login(data.mobile_phone_number, data.verify_code, data.area_code)
        return R.success(data=status, msg="登录成功")
    except Exception as error:
        return provider_error(error)


@router.post("/xiaoyuzhou/auth/logout")
def logout():
    auth_provider.logout()
    return R.success(data=auth_provider.auth_status(), msg="已退出登录")


@router.post("/xiaoyuzhou/search")
def search(data: SearchRequest):
    try:
        result = search_provider.search_episodes(data.keyword, data.load_more_key, data.pid)
        return R.success(data=result)
    except Exception as error:
        return provider_error(error)
