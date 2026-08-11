import importlib.util
import pathlib
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock


BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    module_path = BACKEND_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"{name} module spec not found")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


auth_module = load_module(
    "app.providers.xiaoyuzhou_auth",
    pathlib.Path("app") / "providers" / "xiaoyuzhou_auth.py",
)
search_module = load_module(
    "app.providers.xiaoyuzhou_search",
    pathlib.Path("app") / "providers" / "xiaoyuzhou_search.py",
)
XiaoyuzhouAuthProvider = auth_module.XiaoyuzhouAuthProvider
XiaoyuzhouTokenStore = auth_module.XiaoyuzhouTokenStore
XiaoyuzhouSearchProvider = search_module.XiaoyuzhouSearchProvider


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


class TestXiaoyuzhouSearchProvider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = XiaoyuzhouTokenStore(
            str(pathlib.Path(self.temp_dir.name) / "xiaoyuzhou.json")
        )
        self.session = Mock()
        self.auth = XiaoyuzhouAuthProvider(self.store, self.session)
        self.search = XiaoyuzhouSearchProvider(self.auth)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_login_persists_tokens_without_exposing_them_in_status(self):
        self.session.post.return_value = FakeResponse(
            payload={"data": {"user": {"uid": "user-1", "nickname": "Tester"}}},
            headers={
                "x-jike-access-token": "access-token",
                "x-jike-refresh-token": "refresh-token",
            },
        )

        status = self.auth.login("13100000000", "1234")

        self.assertTrue(status["authenticated"])
        self.assertEqual(status["nickname"], "Tester")
        self.assertNotIn("access_token", status)
        self.assertEqual(self.store.read()["access_token"], "access-token")

    def test_send_code_returns_request_metadata_and_current_client_header(self):
        self.session.post.return_value = FakeResponse(
            payload={"success": True},
            headers={"X-Request-Id": "request-1"},
        )

        result = self.auth.send_code("13100000000")

        self.assertEqual(result["message"], "验证码请求已提交")
        self.assertEqual(result["request_id"], "request-1")
        headers = self.session.post.call_args.kwargs["headers"]
        self.assertEqual(headers["Accept"], "*/*")
        self.assertEqual(headers["x-custom"], "eyJ2ZXJzaW9uIjoiMS4wIn0=")
        self.assertEqual(headers["App-Version"], "2.114.0")
        self.assertEqual(headers["App-BuildNo"], "1576")
        self.assertIn("Xiaoyuzhou/2.114.0", headers["User-Agent"])

    def test_send_code_surfaces_upstream_toast(self):
        self.session.post.return_value = FakeResponse(
            status_code=429,
            payload={"code": 1, "toast": "请求过于频繁，请稍后再试"},
        )

        with self.assertRaises(auth_module.XiaoyuzhouApiError) as context:
            self.auth.send_code("13100000000")

        self.assertEqual(str(context.exception), "请求过于频繁，请稍后再试")

    def test_create_qr_session_returns_validated_session(self):
        self.session.post.return_value = FakeResponse(
            payload={
                "id": "qr-session-1",
                "url": "https://h5.xiaoyuzhoufm.com/oauth?qrcode_id=qr-session-1",
            }
        )

        result = self.auth.create_qr_session()

        self.assertEqual(result["id"], "qr-session-1")
        self.assertEqual(result["status"], "WAITTING")
        self.assertEqual(result["expires_in"], 180)
        request = self.session.post.call_args
        self.assertEqual(request.kwargs["json"], {"clientId": "xyz-web"})
        self.assertEqual(request.kwargs["headers"]["x-midway-app-id"], "v6worU4NnWyL")

    def test_poll_qr_session_keeps_waiting_without_tokens(self):
        self.session.post.return_value = FakeResponse(payload={"status": "WAITTING"})

        result = self.auth.poll_qr_session("qr-session-1")

        self.assertEqual(result, {"status": "WAITTING", "authenticated": False})
        self.assertFalse(self.auth.auth_status()["authenticated"])

    def test_poll_qr_session_saves_confirmed_tokens(self):
        self.session.post.return_value = FakeResponse(
            payload={"status": "CONFIRMED"},
            headers={
                "x-jike-access-token": "qr-access-token",
                "x-jike-refresh-token": "qr-refresh-token",
            },
        )

        result = self.auth.poll_qr_session("qr-session-1")

        self.assertEqual(result, {"status": "CONFIRMED", "authenticated": True})
        stored = self.store.read()
        self.assertEqual(stored["access_token"], "qr-access-token")
        self.assertEqual(stored["refresh_token"], "qr-refresh-token")
        self.assertEqual(stored["auth_method"], "qrcode")

    def test_qr_credentials_refresh_through_web_api(self):
        self.store.save_login(
            "old-access",
            "old-refresh",
            auth_method="qrcode",
        )
        self.session.post.return_value = FakeResponse(
            payload={
                "success": True,
                "x-jike-access-token": "new-access",
                "x-jike-refresh-token": "new-refresh",
            }
        )

        access_token = self.auth.refresh_tokens()

        self.assertEqual(access_token, "new-access")
        request = self.session.post.call_args
        self.assertEqual(
            request.args[0],
            "https://web-api.xiaoyuzhoufm.com/app_auth_tokens.refresh",
        )
        self.assertEqual(request.kwargs["json"], {})
        self.assertEqual(self.store.read()["refresh_token"], "new-refresh")

    def test_search_normalizes_episode_and_returns_pagination_key(self):
        self.store.save_login("access-token", "refresh-token", {})
        self.session.post.return_value = FakeResponse(
            payload={
                "data": [
                    {
                        "type": "EPISODE",
                        "eid": "69b4d2f9f8b8079bfa3ae7f2",
                        "title": "Test episode",
                        "duration": 125,
                        "pubDate": "2026-08-08T08:00:00.000Z",
                        "podcast": {
                            "pid": "podcast-1",
                            "title": "Test podcast",
                            "image": {"picUrl": "https://image.xyzcdn.net/cover.jpg"},
                        },
                    }
                ],
                "loadMoreKey": {"loadMoreKey": 20, "searchId": "search-1"},
            }
        )

        result = self.search.search_episodes("测试")

        self.assertEqual(result["items"][0]["podcast_title"], "Test podcast")
        self.assertEqual(
            result["items"][0]["episode_url"],
            "https://www.xiaoyuzhoufm.com/episode/69b4d2f9f8b8079bfa3ae7f2",
        )
        self.assertEqual(result["load_more_key"]["searchId"], "search-1")
        request_payload = self.session.post.call_args.kwargs["json"]
        self.assertEqual(request_payload["type"], "EPISODE")
        self.assertEqual(request_payload["keyword"], "测试")

    def test_search_refreshes_token_after_401_and_retries(self):
        self.store.save_login("expired", "refresh-token", {})
        auth = self.store.read()
        auth["updated_at"] = int(time.time())
        self.store.write(auth)
        self.session.post.side_effect = [
            FakeResponse(status_code=401),
            FakeResponse(
                payload={
                    "success": True,
                    "x-jike-access-token": "new-access",
                    "x-jike-refresh-token": "new-refresh",
                }
            ),
            FakeResponse(payload={"data": []}),
        ]

        result = self.search.search_episodes("测试")

        self.assertEqual(result["items"], [])
        self.assertEqual(self.store.read()["access_token"], "new-access")
        retry_headers = self.session.post.call_args.kwargs["headers"]
        self.assertEqual(retry_headers["x-jike-access-token"], "new-access")


if __name__ == "__main__":
    unittest.main()
