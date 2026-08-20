import unittest
from bilibili_parser.models import CommentReply, FeaturedComment, video_from_view_data
from bilibili_parser.renderer import build_card_context, format_count


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
