import unittest
from bilibili_parser.models import (
    CommentReply,
    FeaturedComment,
    article_from_api_data,
    audio_from_api_data,
    bangumi_from_api_data,
    dynamic_from_page_state,
    live_from_api_data,
    video_from_view_data,
)
from bilibili_parser.renderer import (
    build_article_card_context,
    build_bangumi_card_context,
    build_bangumi_text_fallback,
    build_card_context,
    build_dynamic_card_context,
    format_count,
)


VIEW_DATA = {
    "bvid": "BV1xx411c7mD",
    "aid": 170001,
    "cid": 279786,
    "title": "测试 <视频>",
    "desc": "第一行\n第二行",
    "pic": "https://i0.hdslb.com/bfs/archive/test.jpg",
    "duration": 125,
    "pubdate": 1700000000,
    "tname": "科技",
    "videos": 2,
    "pages": [
        {"cid": 279786, "part": "第一部分", "duration": 65},
        {"cid": 279787, "part": "第二部分", "duration": 60},
    ],
    "owner": {
        "mid": 123,
        "name": "测试UP主",
        "face": "https://i0.hdslb.com/bfs/face/test.jpg",
    },
    "stat": {
        "view": 12345,
        "danmaku": 99,
        "reply": 88,
        "favorite": 77,
        "coin": 66,
        "share": 55,
        "like": 44,
    },
}


class ModelsAndRendererTests(unittest.TestCase):
    def test_maps_view_payload(self):
        video = video_from_view_data(VIEW_DATA)
        self.assertEqual(video.bvid, "BV1xx411c7mD")
        self.assertEqual(video.owner_name, "测试UP主")
        self.assertEqual(video.page_count, 2)
        self.assertEqual([page.cid for page in video.pages], [279786, 279787])
        self.assertEqual(video.pages[1].title, "第二部分")
        self.assertEqual(video.stats.view, 12345)
        self.assertEqual(video.canonical_url, "https://www.bilibili.com/video/BV1xx411c7mD")

    def test_rejects_incomplete_payload(self):
        with self.assertRaises(ValueError):
            video_from_view_data({"bvid": "BV1xx411c7mD"})

    def test_maps_audio_payload(self):
        audio = audio_from_api_data(
            {
                "id": 10004684671,
                "uid": 3691000742545747,
                "uname": "UP主",
                "author": "作者",
                "title": "测试曲目",
                "cover": "https://i0.hdslb.com/bfs/music/test.jpg",
                "intro": "简介",
                "duration": 254,
                "statistic": {"play": 25255, "collect": 2940, "comment": 347},
            }
        )
        self.assertEqual(audio.au_id, 10004684671)
        self.assertEqual(audio.owner_mid, 3691000742545747)
        self.assertEqual(audio.owner_name, "UP主")
        self.assertEqual(audio.play_count, 25255)
        self.assertEqual(
            audio.canonical_url, "https://www.bilibili.com/audio/au10004684671"
        )

    def test_rejects_incomplete_audio_payload(self):
        with self.assertRaises(ValueError):
            audio_from_api_data({"title": "只有标题"})

    def test_maps_article_payload(self):
        article = article_from_api_data(
            {
                "id": 300010,
                "title": "测试专栏",
                "summary": "摘要内容",
                "banner_url": "https://i0.hdslb.com/bfs/article/banner.jpg",
                "category": {"id": 6, "name": "单机游戏"},
                "author": {"mid": 14211580, "name": "作者甲", "face": "https://i1.hdslb.com/bfs/face/a.jpg"},
                "publish_time": 1700000000,
                "words": 1051,
                "stats": {"view": 4471, "like": 52, "coin": 5, "favorite": 58, "reply": 10, "share": 3},
                "tags": [{"name": "独立游戏"}, {"name": "奇幻"}],
            }
        )
        self.assertEqual(article.article_id, 300010)
        self.assertEqual(article.owner_name, "作者甲")
        self.assertEqual(article.stats.view, 4471)
        self.assertEqual(article.category, "单机游戏")
        self.assertEqual(article.tags, ["独立游戏", "奇幻"])
        self.assertEqual(
            article.canonical_url, "https://www.bilibili.com/read/cv300010"
        )

    def test_maps_live_payload(self):
        live = live_from_api_data(
            {
                "room_id": 5440,
                "uid": 9617619,
                "title": "测试直播间",
                "user_cover": "https://i0.hdslb.com/bfs/live/cover.jpg",
                "online": 1200,
                "live_status": 1,
                "parent_area_name": "虚拟主播",
                "area_name": "虚拟日常",
                "description": "直播简介",
                "tags": "虚拟,歌会",
            }
        )
        self.assertEqual(live.room_id, 5440)
        self.assertEqual(live.owner_mid, 9617619)
        self.assertEqual(live.live_status, 1)
        self.assertEqual(live.online, 1200)
        self.assertEqual(
            live.canonical_url, "https://live.bilibili.com/5440"
        )

    def test_maps_dynamic_page_state(self):
        state = {
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
                                                "word": {"words": "第一行内容"},
                                            }
                                        ]
                                    }
                                },
                                {
                                    "text": {
                                        "nodes": [
                                            {
                                                "type": "TEXT_NODE_TYPE_WORD",
                                                "word": {"words": "第二行内容"},
                                            }
                                        ]
                                    }
                                },
                            ]
                        },
                    },
                    {
                        "module_type": "MODULE_TYPE_TOP",
                        "module_top": {
                            "display": {
                                "album": {
                                    "pics": [
                                        {"url": "https://i0.hdslb.com/bfs/new_dyn/pic.jpg"}
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
        dynamic = dynamic_from_page_state(state)
        self.assertEqual(dynamic.dyn_id, "967717348014293017")
        self.assertEqual(dynamic.author_name, "动态作者")
        self.assertEqual(dynamic.content, "第一行内容\n第二行内容")
        self.assertEqual(dynamic.like_count, 73)
        self.assertEqual(dynamic.images, ["https://i0.hdslb.com/bfs/new_dyn/pic.jpg"])
        self.assertEqual(
            dynamic.canonical_url,
            "https://www.bilibili.com/opus/967717348014293017",
        )

    def test_rejects_incomplete_article_payload(self):
        with self.assertRaises(ValueError):
            article_from_api_data({"title": "只有标题"})

    def test_rejects_incomplete_live_payload(self):
        with self.assertRaises(ValueError):
            live_from_api_data({"title": "没有房间号"})

    def test_rejects_incomplete_dynamic_payload(self):
        with self.assertRaises(ValueError):
            dynamic_from_page_state({"detail": {"modules": []}})

    def test_maps_bangumi_payload(self):
        bangumi = bangumi_from_api_data(
            {
                "season_id": 42202,
                "title": "测试番剧",
                "evaluate": "这是一个测试番剧的简介。",
                "cover": "https://i0.hdslb.com/bfs/bangumi/cover.jpg",
                "total": 12,
                "episodes": [
                    {"ep_id": 836366, "title": "1", "long_title": "第一集"},
                    {"ep_id": 836367, "title": "2", "long_title": "第二集"},
                ],
                "up_info": {"mid": 123, "uname": "制作组", "face": "https://i0.hdslb.com/bfs/face/a.jpg"},
                "stat": {"views": 12000000, "danmakus": 50000, "favorite": 800000, "reply": 40000, "coins": 200000},
                "areas": [{"name": "日本"}],
                "new_ep": {"desc": "已完结, 全12话"},
            },
            ep_id=836366,
        )
        self.assertEqual(bangumi.season_id, 42202)
        self.assertEqual(bangumi.ep_id, 836366)
        self.assertEqual(bangumi.ep_title, "1 第一集")
        self.assertEqual(bangumi.total_episodes, 12)
        self.assertEqual(bangumi.area_names, ["日本"])
        self.assertEqual(bangumi.new_ep_desc, "已完结, 全12话")
        self.assertEqual(bangumi.view, 12000000)
        self.assertEqual(
            bangumi.canonical_url, "https://www.bilibili.com/bangumi/play/ep836366"
        )

    def test_bangumi_canonical_url_falls_back_to_season(self):
        bangumi = bangumi_from_api_data(
            {"season_id": 42202, "title": "测试番剧"}, ep_id=0
        )
        self.assertEqual(bangumi.ep_id, 0)
        self.assertEqual(
            bangumi.canonical_url, "https://www.bilibili.com/bangumi/play/ss42202"
        )
        self.assertEqual(bangumi.canonical_id, "ss42202")

    def test_rejects_incomplete_bangumi_payload(self):
        with self.assertRaises(ValueError):
            bangumi_from_api_data({"title": "只有标题"})

    def test_bangumi_card_context_and_text_fallback(self):
        bangumi = bangumi_from_api_data(
            {
                "season_id": 42202,
                "title": "测试番剧",
                "evaluate": "简介内容",
                "total": 12,
                "areas": [{"name": "日本"}],
                "stat": {"views": 12000000, "danmakus": 50000, "favorite": 800000, "reply": 40000, "coins": 200000},
            },
            ep_id=836366,
        )
        context = build_bangumi_card_context(bangumi)
        self.assertEqual(context["content_type"], "番剧")
        self.assertEqual(context["brand_sub"], "B站番剧解析")
        self.assertEqual(context["body_title"], "剧集简介")
        self.assertEqual(context["body_text"], "简介内容")
        self.assertEqual(context["content_id"], "ep836366")
        self.assertEqual(
            [item["label"] for item in context["meta_items"]],
            ["地区", "集数"],
        )
        self.assertEqual(
            [(item["label"], item["value"]) for item in context["stats"]],
            [
                ("播放", "1200万"),
                ("追番", "80万"),
                ("弹幕", "5万"),
                ("评论", "4万"),
                ("投币", "20万"),
            ],
        )
        text = build_bangumi_text_fallback(bangumi)
        self.assertIn("【B站番剧】测试番剧", text)
        self.assertIn("地区：日本", text)
        self.assertIn("集数：12", text)
        self.assertIn("https://www.bilibili.com/bangumi/play/ep836366", text)

    def test_article_card_context_includes_ai_summary(self):
        article = article_from_api_data(
            {
                "id": 300010,
                "title": "测试专栏",
                "summary": "摘要内容",
                "author": {"mid": 1, "name": "作者甲"},
                "words": 100,
            }
        )
        article.ai_summary = "- 要点一\n- 要点二"
        article.summary_source = "专栏正文"
        context = build_article_card_context(article)
        self.assertEqual(context["ai_summary"], "- 要点一\n- 要点二")
        self.assertEqual(context["summary_source"], "专栏正文")

    def test_dynamic_card_context_includes_ai_summary(self):
        state = {
            "id": "967717348014293017",
            "detail": {
                "modules": [
                    {
                        "module_type": "MODULE_TYPE_AUTHOR",
                        "module_author": {"name": "动态作者", "mid": 1, "pub_ts": 1724152653},
                    },
                    {
                        "module_type": "MODULE_TYPE_CONTENT",
                        "module_content": {
                            "paragraphs": [
                                {
                                    "text": {
                                        "nodes": [
                                            {"type": "TEXT_NODE_TYPE_WORD", "word": {"words": "动态内容"}}
                                        ]
                                    }
                                }
                            ]
                        },
                    },
                ]
            },
        }
        dynamic = dynamic_from_page_state(state)
        dynamic.ai_summary = "AI 总结内容"
        dynamic.summary_source = "动态正文"
        context = build_dynamic_card_context(dynamic)
        self.assertEqual(context["ai_summary"], "AI 总结内容")
        self.assertEqual(context["summary_source"], "动态正文")
        self.assertEqual(context["body_text"], "动态内容")

    def test_count_formatting(self):
        self.assertEqual(format_count(9999), "9999")
        self.assertEqual(format_count(10000), "1万")
        self.assertEqual(format_count(12345), "1.2万")
        self.assertEqual(format_count(100000000), "1亿")

    def test_card_context_escapes_remote_content(self):
        context = build_card_context(video_from_view_data(VIEW_DATA))
        self.assertEqual(context["title"], "测试 &lt;视频&gt;")
        self.assertEqual(context["duration"], "2:05")
        self.assertEqual(context["stats"][0]["value"], "1.2万")
        self.assertEqual(context["cover_src"], "")
        self.assertEqual(context["avatar_src"], "")

    def test_card_context_includes_escaped_featured_comment(self):
        video = video_from_view_data(VIEW_DATA)
        video.featured_comments = [
            FeaturedComment(
                author_name="评论者 <A>",
                author_face_url="https://i0.hdslb.com/bfs/face/comment.jpg",
                content="内容 <script>",
                like_count=12000,
                replies=[
                    CommentReply(
                        author_name="回复者 <B>",
                        author_face_url="https://i0.hdslb.com/bfs/face/reply.jpg",
                        content="回复 <script>",
                    )
                ],
            )
        ]
        context = build_card_context(
            video,
            comment_avatar_srcs={
                "https://i0.hdslb.com/bfs/face/comment.jpg": "data:image/png;base64,comment",
                "https://i0.hdslb.com/bfs/face/reply.jpg": "data:image/png;base64,reply",
            },
        )
        comment = context["featured_comments"][0]
        self.assertEqual(comment["author_name"], "评论者 &lt;A&gt;")
        self.assertEqual(comment["content"], "内容 &lt;script&gt;")
        self.assertEqual(comment["like_count"], "1.2万")
        self.assertEqual(comment["avatar_src"], "data:image/png;base64,comment")
        self.assertEqual(comment["replies"][0]["author_name"], "回复者 &lt;B&gt;")
        self.assertEqual(comment["replies"][0]["content"], "回复 &lt;script&gt;")
        self.assertEqual(comment["replies"][0]["avatar_src"], "data:image/png;base64,reply")


if __name__ == "__main__":
    unittest.main()
