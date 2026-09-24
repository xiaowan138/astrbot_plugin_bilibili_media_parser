import unittest

from bilibili_parser.extractor import (
    extract_video_reference,
    extract_video_references,
)


class DummyJsonComponent:
    def __init__(self, data):
        self.data = data


class ExtractorTests(unittest.TestCase):
    def test_extracts_standard_bvid_url(self):
        result = extract_video_reference(
            "看看 https://www.bilibili.com/video/BV1xx411c7mD?spm_id_from=333.1007"
        )
        self.assertEqual((result.kind, result.value), ("bvid", "BV1xx411c7mD"))

    def test_extracts_av_number(self):
        result = extract_video_reference("av170001")
        self.assertEqual((result.kind, result.value), ("aid", "170001"))

    def test_extracts_protocol_less_short_link(self):
        result = extract_video_reference("复制这条：b23.tv/AbCd123")
        self.assertEqual(result.kind, "url")
        self.assertEqual(result.value, "https://b23.tv/AbCd123")

    def test_extracts_escaped_qq_mini_program_json(self):
        component = DummyJsonComponent(
            {
                "app": "com.tencent.miniapp_01",
                "meta": {
                    "detail_1": {
                        "qqdocurl": "https:\\/\\/b23.tv\\/AbCd123",
                        "title": "测试视频",
                    }
                },
            }
        )
        result = extract_video_reference("", [component])
        self.assertEqual(result.kind, "url")
        self.assertEqual(result.value, "https://b23.tv/AbCd123")

    def test_extracts_url_encoded_small_program_link(self):
        payload = {
            "prompt": "[哔哩哔哩]",
            "jump": "https%3A%2F%2Fwww.bilibili.com%2Fvideo%2FBV1xx411c7mD",
        }
        result = extract_video_reference("", payload)
        self.assertEqual((result.kind, result.value), ("bvid", "BV1xx411c7mD"))

    def test_extracts_bilibili_uri(self):
        result = extract_video_reference("bilibili://video/170001")
        self.assertEqual((result.kind, result.value), ("aid", "170001"))

    def test_ignores_unrelated_url(self):
        self.assertIsNone(extract_video_reference("https://example.com/video/BV123"))

    def test_extracts_audio_au_id(self):
        result = extract_video_reference("au10004684671")
        self.assertEqual((result.kind, result.value), ("auid", "10004684671"))

    def test_extracts_audio_url(self):
        result = extract_video_reference(
            "听听这个 https://www.bilibili.com/audio/au10004684671"
        )
        self.assertEqual((result.kind, result.value), ("auid", "10004684671"))

    def test_extracts_audio_url_with_params(self):
        result = extract_video_reference(
            "https://www.bilibili.com/audio/au10004684671?spm_id_from=333.1007"
        )
        self.assertEqual((result.kind, result.value), ("auid", "10004684671"))

    def test_bvid_takes_priority_over_auid(self):
        """BV should be preferred when both patterns exist in the text."""
        result = extract_video_reference(
            "BV1xx411c7mD au10004684671"
        )
        self.assertEqual((result.kind, result.value), ("bvid", "BV1xx411c7mD"))

    def test_extracts_article_url(self):
        result = extract_video_reference(
            "https://www.bilibili.com/read/cv300010?from=search"
        )
        self.assertEqual((result.kind, result.value), ("article", "300010"))

    def test_extracts_live_url(self):
        result = extract_video_reference(
            "来看看直播 https://live.bilibili.com/12345?spm_id_from=333.999"
        )
        self.assertEqual((result.kind, result.value), ("live", "12345"))

    def test_extracts_live_h5_url(self):
        result = extract_video_reference("https://live.bilibili.com/h5/12345")
        self.assertEqual((result.kind, result.value), ("live", "12345"))

    def test_extracts_live_blanc_url(self):
        result = extract_video_reference(
            "https://live.bilibili.com/blanc/12345?share_source=qq"
        )
        self.assertEqual((result.kind, result.value), ("live", "12345"))

    def test_extracts_live_uri(self):
        result = extract_video_reference("bilibili://live/12345")
        self.assertEqual((result.kind, result.value), ("live", "12345"))

    def test_extracts_opus_uri(self):
        result = extract_video_reference("bilibili://opus/967717348014293017")
        self.assertEqual(
            (result.kind, result.value), ("dynamic", "967717348014293017")
        )

    def test_extracts_article_uri(self):
        result = extract_video_reference("bilibili://article/cv300010")
        self.assertEqual((result.kind, result.value), ("article", "300010"))

    def test_extracts_audio_uri(self):
        result = extract_video_reference("bilibili://audio/au10004684671")
        self.assertEqual((result.kind, result.value), ("auid", "10004684671"))

    def test_extracts_audio_uri_without_prefix(self):
        result = extract_video_reference("bilibili://audio/10004684671")
        self.assertEqual((result.kind, result.value), ("auid", "10004684671"))

    def test_extracts_opus_dynamic_url(self):
        result = extract_video_reference(
            "https://www.bilibili.com/opus/967717348014293017"
        )
        self.assertEqual((result.kind, result.value), ("dynamic", "967717348014293017"))

    def test_extracts_t_bilibili_dynamic_url(self):
        result = extract_video_reference("https://t.bilibili.com/123456")
        self.assertEqual((result.kind, result.value), ("dynamic", "123456"))

    def test_extracts_bangumi_ep_url(self):
        result = extract_video_reference(
            "https://www.bilibili.com/bangumi/play/ep836366?from=search"
        )
        self.assertEqual((result.kind, result.value), ("ep", "836366"))

    def test_extracts_bangumi_ss_url(self):
        result = extract_video_reference(
            "追番 https://www.bilibili.com/bangumi/play/ss42202"
        )
        self.assertEqual((result.kind, result.value), ("ss", "42202"))

    def test_extracts_user_from_space_homepage(self):
        # 空间主页解析成 UP 主名片，不再被静默忽略。
        result = extract_video_reference("https://space.bilibili.com/13157457")
        self.assertEqual((result.kind, result.value), ("user", "13157457"))

    def test_ignores_space_subpage_without_content_id(self):
        # 空间主页的子页（合集、相册等）没有稳定含义，仍然忽略；
        # 带 BV 的 space 链接由更早的分支命中，不受这里影响。
        for url in (
            "https://space.bilibili.com/13157457/channel/collectiondetail?sid=1",
            "https://space.bilibili.com/",
        ):
            with self.subTest(url=url):
                self.assertIsNone(extract_video_reference(url))

    def test_extracts_video_from_space_url_with_bvid(self):
        result = extract_video_reference(
            "https://space.bilibili.com/13157457/video/BV1xx411c7mD"
        )
        self.assertEqual((result.kind, result.value), ("bvid", "BV1xx411c7mD"))


class MultiReferenceExtractionTests(unittest.TestCase):
    def test_extracts_multiple_links_in_order(self):
        references = extract_video_references(
            "看这个 https://www.bilibili.com/video/BV1xx411c7mD "
            "和直播 https://live.bilibili.com/12345 "
            "还有专栏 https://www.bilibili.com/read/cv300010"
        )
        self.assertEqual(
            [(r.kind, r.value) for r in references],
            [
                ("bvid", "BV1xx411c7mD"),
                ("live", "12345"),
                ("article", "300010"),
            ],
        )

    def test_deduplicates_repeated_links(self):
        references = extract_video_references(
            "BV1xx411c7mD 和 https://www.bilibili.com/video/BV1xx411c7mD"
        )
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].kind, "bvid")

    def test_ignores_non_bilibili_urls(self):
        references = extract_video_references(
            "看看 https://example.com/a 和 https://b23.tv/x"
        )
        self.assertEqual(
            [(r.kind, r.value) for r in references],
            [("url", "https://b23.tv/x")],
        )

    def test_extracts_from_nested_json_payload(self):
        payload = {
            "meta": {
                "detail_1": {
                    "qqdocurl": "https://b23.tv/AbCd12",
                    "extra": "https://www.bilibili.com/audio/au10004684671",
                }
            }
        }
        references = extract_video_references(payload)
        self.assertEqual(
            [(r.kind, r.value) for r in references],
            [("url", "https://b23.tv/AbCd12"), ("auid", "10004684671")],
        )


if __name__ == "__main__":
    unittest.main()

