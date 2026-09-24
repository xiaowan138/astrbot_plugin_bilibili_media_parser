"""Runtime tests for main.py.

The older contract tests only grep main.py for source strings, so they cannot
see an AttributeError that happens while a card is built. These tests import
the real main.py against a stubbed astrbot, render the real Jinja templates and
assert on the produced HTML.
"""

import asyncio
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import Template

from astrbot_stub import load_plugin_main

PLUGIN = load_plugin_main()
MODELS = __import__(
    "astrbot_plugin_bilibili_media_parser.bilibili_parser.models",
    fromlist=["models"],
)
EXTRACTOR = __import__(
    "astrbot_plugin_bilibili_media_parser.bilibili_parser.extractor",
    fromlist=["extractor"],
)

VIEW_DATA = {
    "bvid": "BV1xx411c7mD",
    "aid": 170001,
    "cid": 279786,
    "title": "测试视频标题",
    "desc": "简介",
    "pic": "https://i0.hdslb.com/bfs/archive/test.jpg",
    "duration": 125,
    "pubdate": 1700000000,
    "tname": "科技",
    "videos": 3,
    "pages": [
        {"cid": 279786, "part": "第一部分", "duration": 65},
        {"cid": 279787, "part": "第二部分", "duration": 60},
        {"cid": 279788, "part": "第三部分", "duration": 55},
    ],
    "owner": {"mid": 123, "name": "测试UP主", "face": "https://i0.hdslb.com/bfs/face/a.jpg"},
    "stat": {"view": 1, "danmaku": 2, "reply": 3, "favorite": 4, "coin": 5, "share": 6, "like": 7},
}
SINGLE_PAGE_VIEW_DATA = {**VIEW_DATA, "videos": 1, "pages": [VIEW_DATA["pages"][0]]}

ARTICLE_DATA = {
    "id": 300010,
    "title": "测试专栏",
    "summary": "专栏摘要",
    "banner_url": "https://i0.hdslb.com/bfs/article/cover.jpg",
    "category": {"name": "科技"},
    "author": {"name": "专栏作者", "mid": 555, "face": "https://i0.hdslb.com/bfs/face/b.jpg"},
    "publish_time": 1700000000,
    "words": 1200,
    "stats": {"view": 10, "like": 20, "coin": 30, "favorite": 40, "reply": 50, "share": 60},
    "tags": [{"name": "标签一"}],
    "content": "<p>正文第一段</p>",
}

LIVE_DATA = {
    "room_id": 5440,
    "title": "测试直播间",
    "uid": 9617619,
    "user_name": "主播",
    "user_cover": "https://i0.hdslb.com/bfs/live/cover.jpg",
    "online": 1200,
    "live_status": 1,
    "area_name": "歌会",
    "parent_area_name": "娱乐",
    "description": "直播简介",
    "tags": "虚拟,歌会",
}

BANGUMI_DATA = {
    "season_id": 42202,
    "title": "测试番剧",
    "evaluate": "剧集简介",
    "cover": "https://i0.hdslb.com/bfs/bangumi/cover.jpg",
    "total": 2,
    "areas": [{"name": "日本"}],
    "new_ep": {"desc": "更新至2集"},
    "up_info": {"uname": "哔哩哔哩", "mid": 73, "face": "https://i0.hdslb.com/bfs/face/c.jpg"},
    "stat": {"views": 100, "danmakus": 10, "favorite": 20, "reply": 30, "coins": 40},
    "episodes": [
        {"ep_id": 1001, "title": "第1话", "long_title": "开端"},
        {"ep_id": 1002, "title": "第2话", "long_title": "结局"},
    ],
}

DYNAMIC_STATE_TWO_PICS = {
    "id": "967717348014293017",
    "detail": {
        "modules": [
            {
                "module_type": "MODULE_TYPE_AUTHOR",
                "module_author": {
                    "name": "动态作者",
                    "mid": 645769214,
                    "face": "https://i2.hdslb.com/bfs/face/f.jpg",
                    "pub_ts": 1724152653,
                },
            },
            {
                "module_type": "MODULE_TYPE_CONTENT",
                "module_content": {
                    "paragraphs": [
                        {
                            "text": {
                                "nodes": [
                                    {
                                        "type": "TEXT_NODE_TYPE_WORD",
                                        "word": {"words": "动态正文内容"},
                                    }
                                ]
                            }
                        }
                    ]
                },
            },
            {
                "module_type": "MODULE_TYPE_TOP",
                "module_top": {
                    "display": {
                        "album": {
                            "pics": [
                                {"url": "https://i0.hdslb.com/bfs/new_dyn/pic0.jpg"},
                                {"url": "https://i0.hdslb.com/bfs/new_dyn/pic1.jpg"},
                                {"url": "https://i0.hdslb.com/bfs/new_dyn/pic2.jpg"},
                            ]
                        }
                    }
                },
            },
            {
                "module_type": "MODULE_TYPE_STAT",
                "module_stat": {
                    "like": {"count": 73},
                    "comment": {"count": 43},
                    "forward": {"count": 2},
                    "favorite": {"count": 28},
                },
            },
        ]
    },
}

USER_DATA = {
    "card": {
        "mid": "13157457",
        "name": "某UP主",
        "face": "https://i0.hdslb.com/bfs/face/u.jpg",
        "sign": "一个做视频的人",
        "fans": 12000,
        "attention": 88,
        "level_info": {"current_level": 6},
        "official": {"title": "认证机构", "type": 1},
    },
    "follower": 12345,
    "archive_count": 120,
    "like_num": 456789,
}


class FakeContext:
    def __init__(self) -> None:
        self.sent = []
        self.llm_calls = 0

    async def send_message(self, umo, chain):
        self.sent.append((umo, chain))

    async def get_current_chat_provider_id(self, umo=None):
        return "fake-provider"

    async def llm_generate(self, **_kwargs):
        self.llm_calls += 1

        class _Response:
            completion_text = "这是模型生成的概要"

        return _Response()


class FakeEvent:
    def __init__(self, message: str = "", sender: str = "10001") -> None:
        self.message_str = message
        self.unified_msg_origin = "fake:GroupMessage:1"
        self.stopped = False
        self.results = []
        self.message_obj = type("Obj", (), {"raw_message": message, "message": []})()

    def get_messages(self):
        return []

    def get_sender_id(self):
        return self.sender_id_for_test

    def get_self_id(self):
        return "bot"

    def is_admin(self):
        return False

    def plain_result(self, text):
        self.results.append(("plain", text))
        return text

    def chain_result(self, chain):
        self.results.append(("chain", chain))
        return chain

    def stop_event(self):
        self.stopped = True


FakeEvent.sender_id_for_test = "10001"


def make_plugin(**config) -> PLUGIN.BilibiliParserPlugin:
    settings = {
        "enable_video_download": False,
        "enable_audio_download": False,
        "enable_ai_summary": False,
        "enable_live_monitor": False,
        "enable_live_end_notify": False,
        "enable_manual_summary": False,
        "card_cache_seconds": 300,
        "video_cache_seconds": 300,
        "summary_cache_seconds": 86400,
    }
    settings.update(config)
    return PLUGIN.BilibiliParserPlugin(FakeContext(), settings)


class CardRenderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.plugin = make_plugin()
        self.plugin.html_render = self._html_render
        self.plugin._client.fetch_image_data_uri = self._fetch_image

    async def _html_render(self, template, data, return_url=True, options=None):
        # AstrBot 渲染时不自动转义，插件自己 escape 了所有取值。
        html = Template(template).render(**data)
        path = Path(self.tmp.name) / f"card_{len(os.listdir(self.tmp.name))}.jpg"
        path.write_text(html, encoding="utf-8")
        return str(path)

    async def _fetch_image(self, url, **_kwargs):
        return "" if not url else "data:image/jpeg;base64,AAAA"

    def render_content(self, kind, info):
        path = asyncio.run(self.plugin._render_content_card(kind, info))
        return Path(path).read_text(encoding="utf-8")

    def test_every_content_kind_renders_a_card(self):
        cases = {
            "专栏": MODELS.article_from_api_data(ARTICLE_DATA),
            "直播": MODELS.live_from_api_data(LIVE_DATA),
            "番剧": MODELS.bangumi_from_api_data(BANGUMI_DATA, ep_id=1002),
            "动态": MODELS.dynamic_from_page_state(DYNAMIC_STATE_TWO_PICS),
            "UP 主": MODELS.user_from_card_data(USER_DATA, mid=13157457),
        }
        kinds = {"article": "专栏", "live": "直播", "ep": "番剧", "dynamic": "动态", "user": "UP 主"}
        for kind, label in kinds.items():
            with self.subTest(kind=kind):
                html = self.render_content(kind, cases[label])
                self.assertIn("<html", html)
                self.assertIn("topbar", html)

    def test_dynamic_card_renders_cover_and_gallery_without_duplicates(self):
        dynamic = MODELS.dynamic_from_page_state(DYNAMIC_STATE_TWO_PICS)
        self.assertEqual(dynamic.cover_url, "https://i0.hdslb.com/bfs/new_dyn/pic0.jpg")
        html = self.render_content("dynamic", dynamic)
        self.assertIn("B站动态解析", html)
        self.assertIn('class="gallery"', html)
        # 封面已经用了第 1 张，图集只应剩下 2 张。
        gallery = html.split('class="gallery"', 1)[1].split("</div>", 1)[0]
        self.assertEqual(gallery.count("<img"), 2)

    def test_user_card_omits_cover_placeholder(self):
        user = MODELS.user_from_card_data(USER_DATA, mid=13157457)
        html = self.render_content("user", user)
        self.assertIn("B站UP主解析", html)
        self.assertIn("某UP主", html)
        self.assertIn("1.2万", html)
        self.assertNotIn("封面暂时无法加载", html)

    def test_cover_placeholder_still_shown_when_download_fails(self):
        live = MODELS.live_from_api_data(LIVE_DATA)

        async def broken_image(url, **_kwargs):
            return ""

        self.plugin._client.fetch_image_data_uri = broken_image
        html = self.render_content("live", live)
        self.assertIn("封面暂时无法加载", html)

    def test_video_card_lists_parts_for_multi_p(self):
        video = MODELS.video_from_view_data(VIEW_DATA)
        path = asyncio.run(self.plugin._render_card(video))
        html = Path(path).read_text(encoding="utf-8")
        self.assertIn("分 P 列表", html)
        self.assertIn("第一部分", html)
        self.assertIn("第三部分", html)

    def test_single_page_video_omits_part_list(self):
        video = MODELS.video_from_view_data(SINGLE_PAGE_VIEW_DATA)
        path = asyncio.run(self.plugin._render_card(video))
        html = Path(path).read_text(encoding="utf-8")
        self.assertNotIn("分 P 列表", html)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.plugin = make_plugin(enable_ai_summary=True)

    def test_summary_is_cached_between_parses(self):
        subtitle_calls = []

        async def fake_subtitle(video, **_kwargs):
            subtitle_calls.append(video.bvid)
            return "可用的字幕文本"

        self.plugin._client.fetch_public_subtitle = fake_subtitle
        video = MODELS.video_from_view_data(VIEW_DATA)
        event = FakeEvent()

        first = asyncio.run(self.plugin._with_optional_summary(event, video))
        second = asyncio.run(self.plugin._with_optional_summary(event, video))

        self.assertEqual(first.summary, "这是模型生成的概要")
        self.assertEqual(second.summary, "这是模型生成的概要")
        self.assertEqual(len(subtitle_calls), 1)
        self.assertEqual(self.plugin.context.llm_calls, 1)

    def test_manual_summary_command_bypasses_the_global_switch(self):
        async def fake_subtitle(video, **_kwargs):
            return "可用的字幕文本"

        async def fake_resolve(reference):
            return PLUGIN.ResolvedVideo("bvid", reference.value)

        self.plugin._client.fetch_public_subtitle = fake_subtitle
        self.plugin._client.resolve_reference = fake_resolve
        video = MODELS.video_from_view_data(VIEW_DATA)

        async def fake_video_info(_resolved):
            return video

        self.plugin._get_video_info = fake_video_info

        event = FakeEvent()
        asyncio.run(
            _drain(self.plugin._handle_manual_summary(event, "BV1xx411c7mD"))
        )
        text = "\n".join(item[1] for item in event.results)
        self.assertIn("【B站视频概要】测试视频标题", text)
        self.assertIn("这是模型生成的概要", text)

    def test_manual_summary_disabled_returns_no_match(self):
        plugin = make_plugin(enable_ai_summary=False)
        self.assertIsNone(plugin._parse_summary_command("视频总结 BV1xx411c7mD"))

    def test_manual_summary_enabled_parses_target(self):
        plugin = make_plugin(enable_manual_summary=True)
        self.assertEqual(
            plugin._parse_summary_command("视频总结 BV1xx411c7mD"), "BV1xx411c7mD"
        )
        self.assertEqual(plugin._parse_summary_command("视频总结"), "")
        self.assertIsNone(plugin._parse_summary_command("视频下载 123456"))


async def _drain(generator) -> None:
    async for _result in generator:
        pass


class MessageHandlingTests(unittest.TestCase):
    def test_download_command_tolerates_surrounding_whitespace(self):
        plugin = make_plugin(enable_video_download=True)
        event = FakeEvent("视频下载 123456 ")

        async def run():
            async for _ in plugin.on_message(event):
                pass

        asyncio.run(run())
        self.assertTrue(event.stopped, "命令没有被识别，事件也没有被终止")
        text = "\n".join(item[1] for item in event.results)
        self.assertIn("编号", text)

    def test_plain_chat_message_is_not_consumed(self):
        plugin = make_plugin()
        event = FakeEvent("大家晚上好")

        async def run():
            async for _ in plugin.on_message(event):
                pass

        asyncio.run(run())
        self.assertFalse(event.stopped)
        self.assertEqual(event.results, [])

    def test_extra_links_are_reported_instead_of_dropped_silently(self):
        plugin = make_plugin(max_links_per_message=1)

        async def fake_dispatch(event, reference):
            yield event.plain_result(f"已解析 {reference.value}")

        plugin._dispatch_reference = fake_dispatch
        event = FakeEvent(
            "https://www.bilibili.com/video/BV1xx411c7mD "
            "https://www.bilibili.com/video/BV1xx411c7mE "
            "https://www.bilibili.com/video/BV1xx411c7mF"
        )

        async def run():
            async for _ in plugin.on_message(event):
                pass

        asyncio.run(run())
        text = "\n".join(item[1] for item in event.results)
        self.assertIn("只解析了前 1 个", text)
        self.assertIn("剩余 2 个", text)


class RoutingTests(unittest.TestCase):
    def test_space_link_routes_to_the_content_card_flow(self):
        plugin = make_plugin()
        seen = []

        async def fake_content_card(event, reference, **kwargs):
            seen.append(reference.kind)
            yield event.plain_result("ok")

        plugin._handle_content_card = fake_content_card
        event = FakeEvent()
        reference = EXTRACTOR.VideoReference("user", "13157457")
        asyncio.run(_drain(plugin._dispatch_reference(event, reference)))
        self.assertEqual(seen, ["user"])

    def test_live_monitor_starts_without_any_message(self):
        async def run():
            plugin = make_plugin(enable_live_monitor=True)
            self.assertIsNotNone(plugin._live_monitor_task)
            self.assertFalse(plugin._live_monitor_task.done())
            plugin._live_monitor_task.cancel()
            try:
                await plugin._live_monitor_task
            except asyncio.CancelledError:
                pass

        asyncio.run(run())

    def test_live_monitor_stays_stopped_when_disabled(self):
        async def run():
            plugin = make_plugin()
            self.assertIsNone(plugin._live_monitor_task)

        asyncio.run(run())


class DownloadSlotTests(unittest.TestCase):
    def test_queue_wait_releases_on_cancel(self):
        plugin = make_plugin(video_download_max_concurrency=1)

        async def run():
            await plugin._download_semaphore.acquire()
            job = PLUGIN.DownloadJob(
                time.monotonic(), 1, cancel_event=asyncio.Event()
            )
            task = asyncio.create_task(plugin._acquire_download_slot(job))
            # 至少走完一轮 0.5 秒 wait_for 超时，覆盖排队轮询分支。
            await asyncio.sleep(0.7)
            job.cancel_event.set()
            return await task

        self.assertFalse(asyncio.run(run()))


if __name__ == "__main__":
    unittest.main()
