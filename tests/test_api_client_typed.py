import asyncio
import unittest

from bilibili_parser.api_client import BilibiliApiClient, BilibiliApiError
from bilibili_parser.extractor import VideoReference


def _run(coro):
    return asyncio.run(coro)


class _FakeRedirectSession:
    closed = False

    def __init__(self, location):
        self.location = location

    def get(self, url, **kwargs):
        class _Response:
            status = 302
            headers = {"Location": self.location}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        return _Response()


class BangumiResolutionTests(unittest.TestCase):
    def _resolve(self, location):
        client = BilibiliApiClient()
        client._session = _FakeRedirectSession(location)
        return _run(
            client.resolve_reference(VideoReference("url", "https://b23.tv/AbCd12"))
        )

    def test_short_link_to_bangumi_ep_resolves_to_ep_kind(self):
        resolved = self._resolve("https://www.bilibili.com/bangumi/play/ep836366")
        self.assertEqual((resolved.kind, resolved.value), ("ep", "836366"))

    def test_short_link_to_bangumi_ss_resolves_to_ss_kind(self):
        resolved = self._resolve(
            "https://www.bilibili.com/bangumi/play/ss42202?from=search"
        )
        self.assertEqual((resolved.kind, resolved.value), ("ss", "42202"))


BANGUMI_SEASON_PAYLOAD = {
    "season_id": 42202,
    "title": "测试番剧",
    "evaluate": "这是一个测试番剧的简介。",
    "cover": "https://i0.hdslb.com/bfs/archive/season.jpg",
    "stat": {"views": 1234567, "danmakus": 8888, "favorite": 9999, "reply": 777, "coins": 666},
    "areas": [{"name": "日本"}],
    "new_ep": {"desc": "已完结, 全12话"},
    "episodes": [
        {"ep_id": 836366, "title": "第一话", "long_title": "开始"},
        {"ep_id": 836367, "title": "第二话", "long_title": "继续"},
    ],
    "up_info": {"mid": 123, "uname": "测试UP主", "face": "https://i0.hdslb.com/bfs/face/a.jpg"},
}


class BangumiFetchTests(unittest.TestCase):
    def test_fetch_bangumi_info_maps_season_payload(self):
        client = BilibiliApiClient()

        async def fake_get_pgc_json(path, params):
            self.assertEqual(path, "/pgc/view/web/season")
            self.assertEqual(params, {"ep_id": 836366})
            return BANGUMI_SEASON_PAYLOAD

        client._get_pgc_json = fake_get_pgc_json
        bangumi = _run(client.fetch_bangumi_info(VideoReference("ep", "836366")))
        self.assertEqual(bangumi.season_id, 42202)
        self.assertEqual(bangumi.ep_id, 836366)
        self.assertEqual(bangumi.title, "测试番剧")
        self.assertEqual(bangumi.ep_title, "第一话 开始")
        self.assertEqual(bangumi.new_ep_desc, "已完结, 全12话")
        self.assertEqual(bangumi.total_episodes, 2)
        self.assertEqual(bangumi.area_names, ["日本"])
        self.assertEqual(bangumi.owner_name, "测试UP主")
        self.assertEqual(bangumi.view, 1234567)
        self.assertEqual(
            bangumi.canonical_url, "https://www.bilibili.com/bangumi/play/ep836366"
        )

    def test_fetch_bangumi_info_uses_season_param_for_ss(self):
        client = BilibiliApiClient()

        async def fake_get_pgc_json(path, params):
            self.assertEqual(params, {"season_id": 42202})
            return BANGUMI_SEASON_PAYLOAD

        client._get_pgc_json = fake_get_pgc_json
        bangumi = _run(client.fetch_bangumi_info(VideoReference("ss", "42202")))
        # ss 链接没有具体分集，ep_id 保持 0，canonical URL 回退到 ss 形式。
        self.assertEqual(bangumi.ep_id, 0)
        self.assertEqual(
            bangumi.canonical_url, "https://www.bilibili.com/bangumi/play/ss42202"
        )

    def test_fetch_bangumi_info_rejects_wrong_kind(self):
        client = BilibiliApiClient()
        with self.assertRaises(BilibiliApiError):
            _run(client.fetch_bangumi_info(VideoReference("bvid", "BV1xx411c7mD")))

    def test_fetch_bangumi_info_rejects_non_numeric_id(self):
        client = BilibiliApiClient()
        with self.assertRaises(BilibiliApiError):
            _run(client.fetch_bangumi_info(VideoReference("ep", "abc")))


class AudioPlayUrlTests(unittest.TestCase):
    def test_fetch_audio_play_url_returns_first_allowed_url(self):
        client = BilibiliApiClient()

        async def fake_get_json_url(url, params=None, **kwargs):
            self.assertIn("/audio/music-service-c/web/url", url)
            self.assertEqual(params["sid"], 10004684671)
            return {
                "code": 0,
                "data": {
                    "cdns": [
                        "http://upos-sz-mirrorcos.bilivideo.com/song.m4a",
                        "https://upos-sz-mirrorcos.bilivideo.com/song.m4a",
                    ]
                },
            }

        client._get_json_url = fake_get_json_url
        url = _run(client.fetch_audio_play_url(10004684671))
        self.assertEqual(
            url, "https://upos-sz-mirrorcos.bilivideo.com/song.m4a"
        )

    def test_fetch_audio_play_url_rejects_api_error(self):
        client = BilibiliApiClient()

        async def fake_get_json_url(url, params=None, **kwargs):
            return {"code": -400, "msg": "音频不存在"}

        client._get_json_url = fake_get_json_url
        with self.assertRaises(BilibiliApiError):
            _run(client.fetch_audio_play_url(10004684671))


class LiveStatusTests(unittest.TestCase):
    def test_fetch_live_status_returns_status_and_title(self):
        client = BilibiliApiClient()

        async def fake_get_json_url(url, params=None, **kwargs):
            self.assertIn("/room/v1/Room/get_info", url)
            self.assertEqual(params, {"room_id": 12345})
            return {
                "code": 0,
                "data": {"live_status": 1, "title": "测试直播标题"},
            }

        client._get_json_url = fake_get_json_url
        self.assertEqual(
            _run(client.fetch_live_status(12345)), (1, "测试直播标题")
        )

    def test_fetch_live_status_propagates_api_error(self):
        client = BilibiliApiClient()

        async def fake_get_json_url(url, params=None, **kwargs):
            return {"code": 60004, "message": "直播间不存在"}

        client._get_json_url = fake_get_json_url
        with self.assertRaises(BilibiliApiError):
            _run(client.fetch_live_status(12345))


if __name__ == "__main__":
    unittest.main()
