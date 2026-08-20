import unittest

from bilibili_parser.extractor import extract_video_reference


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


if __name__ == "__main__":
    unittest.main()

