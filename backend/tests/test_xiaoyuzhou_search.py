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
