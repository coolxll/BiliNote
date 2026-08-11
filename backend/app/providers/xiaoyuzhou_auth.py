import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests


API_BASE_URL = "https://api.xiaoyuzhoufm.com"
QR_API_BASE_URL = "https://web-api.xiaoyuzhoufm.com/v1"
QR_REFRESH_URL = "https://web-api.xiaoyuzhoufm.com/app_auth_tokens.refresh"
QR_APP_ID = "v6worU4NnWyL"
QR_CLIENT_ID = "xyz-web"
TOKEN_REFRESH_AGE_SECONDS = 20 * 60
X_CUSTOM_HEADER = "eyJ2ZXJzaW9uIjoiMS4wIn0="
APP_VERSION = "2.114.0"
APP_BUILD_NO = "1576"
IOS_VERSION = "17.4.1"


class XiaoyuzhouApiError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class XiaoyuzhouAuthenticationRequired(XiaoyuzhouApiError):
    def __init__(self, message: str = "请先在设置中登录小宇宙"):
        super().__init__(message, status_code=401)


class XiaoyuzhouTokenStore:
    """Persist Xiaoyuzhou credentials on the backend only."""

    def __init__(self, filepath: str = "config/xiaoyuzhou.json"):
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _read_unlocked(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as config_file:
                value = json.load(config_file)
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def read(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._read_unlocked())

    def write(self, data: Dict[str, Any]) -> None:
        with self._lock:
            temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            with temp_path.open("w", encoding="utf-8") as config_file:
                json.dump(data, config_file, ensure_ascii=False, indent=2)
            try:
                os.chmod(temp_path, 0o600)
            except OSError:
                pass
            os.replace(temp_path, self.path)

    def get_or_create_device_id(self) -> str:
        with self._lock:
            data = self._read_unlocked()
            device_id = data.get("device_id")
            if not isinstance(device_id, str) or not device_id:
                device_id = str(uuid.uuid4()).upper()
                data["device_id"] = device_id
                self.write(data)
            return device_id

    def save_login(
        self,
        access_token: str,
        refresh_token: str,
        user: Optional[Dict[str, Any]] = None,
        auth_method: str = "sms",
    ) -> None:
        data = self.read()
        data.update(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "updated_at": int(time.time()),
                "uid": (user or {}).get("uid", ""),
                "nickname": (user or {}).get("nickname", ""),
                "auth_method": auth_method,
            }
        )
        self.write(data)

    def clear_login(self) -> None:
        data = self.read()
        device_id = data.get("device_id")
        self.write({"device_id": device_id} if device_id else {})

    def public_status(self) -> Dict[str, Any]:
        data = self.read()
        return {
            "authenticated": bool(data.get("access_token") and data.get("refresh_token")),
            "uid": data.get("uid", ""),
            "nickname": data.get("nickname", ""),
            "updated_at": data.get("updated_at"),
        }


class XiaoyuzhouAuthProvider:
    def __init__(
        self,
        token_store: Optional[XiaoyuzhouTokenStore] = None,
        session: Optional[requests.Session] = None,
    ):
        self.token_store = token_store or XiaoyuzhouTokenStore()
        self.session = session or requests.Session()
        self._refresh_lock = threading.RLock()

    def auth_status(self) -> Dict[str, Any]:
        return self.token_store.public_status()

    def send_code(self, mobile_phone_number: str, area_code: str = "+86") -> Dict[str, str]:
        response = self.session.post(
            f"{API_BASE_URL}/v1/auth/sendCode",
            json={"mobilePhoneNumber": mobile_phone_number, "areaCode": area_code},
            headers=self.headers(),
            timeout=30,
        )
        self.raise_for_response(response, "发送验证码失败")
        payload = self.response_json(response)
        business_code = payload.get("code")
        if payload.get("success") is False or (
            isinstance(business_code, int) and business_code != 0
        ):
            raise XiaoyuzhouApiError(self.response_message(payload, "发送验证码失败"))
        return {
            "message": self.response_message(payload, "验证码请求已提交"),
            "request_id": response.headers.get("X-Request-Id", ""),
        }

    def create_qr_session(self) -> Dict[str, Any]:
        response = self.session.post(
            f"{QR_API_BASE_URL}/auth/qrcode/create",
            json={"clientId": QR_CLIENT_ID},
            headers=self.qr_headers(),
            timeout=30,
        )
        self.raise_for_response(response, "创建小宇宙登录二维码失败")
        payload = self.response_json(response)
        qrcode_id = payload.get("id")
        qrcode_url = payload.get("url")
        if not isinstance(qrcode_id, str) or not qrcode_id:
            raise XiaoyuzhouApiError("小宇宙未返回二维码会话 ID")
        if not isinstance(qrcode_url, str) or not qrcode_url.startswith(
            "https://h5.xiaoyuzhoufm.com/oauth?"
        ):
            raise XiaoyuzhouApiError("小宇宙返回了无效的二维码地址")
        return {
            "id": qrcode_id,
            "url": qrcode_url,
            "status": "WAITTING",
            "expires_in": 180,
        }

    def poll_qr_session(self, qrcode_id: str) -> Dict[str, Any]:
        response = self.session.post(
            f"{QR_API_BASE_URL}/auth/qrcode/login",
            json={"id": qrcode_id},
            headers=self.qr_headers(),
            timeout=30,
        )
        self.raise_for_response(response, "查询小宇宙扫码状态失败")
        payload = self.response_json(response)
        status = str(payload.get("status") or "UNKNOWN").upper()
        access_token = response.headers.get("x-jike-access-token", "")
        refresh_token = response.headers.get("x-jike-refresh-token", "")
        authenticated = bool(access_token and refresh_token)
        if authenticated:
            self.token_store.save_login(
                access_token,
                refresh_token,
                auth_method="qrcode",
            )
            status = "CONFIRMED"
        return {
            "status": status,
            "authenticated": authenticated,
        }

    def login(
        self,
        mobile_phone_number: str,
        verify_code: str,
        area_code: str = "+86",
    ) -> Dict[str, Any]:
        response = self.session.post(
            f"{API_BASE_URL}/v1/auth/loginOrSignUpWithSMS",
            json={
                "areaCode": area_code,
                "verifyCode": verify_code,
                "mobilePhoneNumber": mobile_phone_number,
            },
            headers=self.headers(),
            timeout=30,
        )
        self.raise_for_response(response, "小宇宙登录失败")
        access_token = response.headers.get("x-jike-access-token", "")
        refresh_token = response.headers.get("x-jike-refresh-token", "")
        if not access_token or not refresh_token:
            raise XiaoyuzhouApiError("登录成功，但小宇宙未返回完整 token")

        payload = self.response_json(response)
        user = payload.get("data", {}).get("user", {})
        if not isinstance(user, dict):
            user = {}
        self.token_store.save_login(access_token, refresh_token, user)
        return self.auth_status()

    def logout(self) -> None:
        self.token_store.clear_login()

    def access_token(self) -> str:
        auth = self.token_store.read()
        access_token = auth.get("access_token")
        refresh_token = auth.get("refresh_token")
        if not access_token or not refresh_token:
            raise XiaoyuzhouAuthenticationRequired()
        updated_at = auth.get("updated_at")
        if isinstance(updated_at, (int, float)) and time.time() - updated_at > TOKEN_REFRESH_AGE_SECONDS:
            return self.refresh_tokens()
        return access_token

    def refresh_tokens(self) -> str:
        with self._refresh_lock:
            auth = self.token_store.read()
            refresh_token = auth.get("refresh_token")
            if not refresh_token:
                raise XiaoyuzhouAuthenticationRequired()
            auth_method = str(auth.get("auth_method") or "sms")
            candidates = []
            if auth_method == "qrcode":
                candidates.append(
                    (
                        QR_REFRESH_URL,
                        {
                            **self.qr_headers(),
                            "x-jike-access-token": str(auth.get("access_token") or ""),
                            "x-jike-refresh-token": str(refresh_token),
                        },
                        True,
                    )
                )
            candidates.append(
                (
                    f"{API_BASE_URL}/app_auth_tokens.refresh",
                    self.headers(
                        access_token=auth.get("access_token"),
                        refresh_token=refresh_token,
                        content_type="application/x-www-form-urlencoded; charset=utf-8",
                    ),
                    False,
                )
            )

            last_message = "小宇宙登录已失效，请重新登录"
            for url, headers, send_json in candidates:
                response = self.session.post(
                    url,
                    headers=headers,
                    json={} if send_json else None,
                    timeout=30,
                )
                if not 200 <= response.status_code < 300:
                    last_message = self.response_message(
                        self.response_json(response),
                        last_message,
                    )
                    continue
                payload = self.response_json(response)
                access_token = payload.get("x-jike-access-token") or response.headers.get(
                    "x-jike-access-token"
                )
                new_refresh_token = payload.get("x-jike-refresh-token") or response.headers.get(
                    "x-jike-refresh-token"
                )
                if access_token and new_refresh_token:
                    self.token_store.save_login(
                        access_token,
                        new_refresh_token,
                        auth,
                        auth_method=auth_method,
                    )
                    return access_token
                last_message = "token 刷新未返回完整凭据"
            raise XiaoyuzhouAuthenticationRequired(last_message)

    def headers(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        content_type: str = "application/json",
    ) -> Dict[str, str]:
        headers = {
            "User-Agent": (
                f"Xiaoyuzhou/{APP_VERSION} (build:{APP_BUILD_NO}; iOS {IOS_VERSION})"
            ),
            "Market": "AppStore",
            "App-BuildNo": APP_BUILD_NO,
            "OS": "ios",
            "x-jike-device-id": self.token_store.get_or_create_device_id(),
            "Manufacturer": "Apple",
            "BundleID": "app.podcast.cosmos",
            "abtest-info": '{"old_user_discovery_feed":"enable"}',
            "Accept-Language": "zh-Hans-CN;q=1.0",
            "Model": "iPhone14,2",
            "app-permissions": "4",
            "Accept": "*/*",
            "Content-Type": content_type,
            "App-Version": APP_VERSION,
            "WifiConnected": "true",
            "OS-Version": IOS_VERSION,
            "Local-Time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "Timezone": "Asia/Shanghai",
            "x-custom": X_CUSTOM_HEADER,
        }
        if access_token:
            headers["x-jike-access-token"] = access_token
        if refresh_token:
            headers["x-jike-refresh-token"] = refresh_token
        return headers

    @staticmethod
    def qr_headers() -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-midway-app-id": QR_APP_ID,
            "Origin": "https://accounts.xiaoyuzhoufm.com",
            "Referer": "https://accounts.xiaoyuzhoufm.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
        }

    @staticmethod
    def response_json(response) -> Dict[str, Any]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except (ValueError, json.JSONDecodeError):
            return {}

    @staticmethod
    def response_message(payload: Dict[str, Any], fallback: str) -> str:
        for key in ("toast", "message", "msg", "error_message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return fallback

    @classmethod
    def raise_for_response(cls, response, fallback_message: str) -> None:
        if 200 <= response.status_code < 300:
            return
        payload = cls.response_json(response)
        message = cls.response_message(payload, fallback_message)
        if response.status_code == 401:
            raise XiaoyuzhouAuthenticationRequired(message)
        raise XiaoyuzhouApiError(message, response.status_code)
