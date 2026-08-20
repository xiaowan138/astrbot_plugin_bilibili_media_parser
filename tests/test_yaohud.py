import unittest

from bilibili_parser.yaohud import find_direct_media_url


class YaohudAdapterTests(unittest.TestCase):
    def test_finds_nested_bilivideo_url(self):
        payload = {
            "video": {
                "pages": [
                    {
                        "play_url": "https://upos-sz-mirror.example.bilivideo.com/video.m4s"
                    }
                ]
            }
        }
        self.assertEqual(
            find_direct_media_url(payload),
            "https://upos-sz-mirror.example.bilivideo.com/video.m4s",
        )

    def test_rejects_non_media_and_non_https_urls(self):
        payload = {
            "cover": "https://i0.hdslb.com/cover.jpg",
            "url": "http://example.bilivideo.com/video.mp4",
            "evil": "https://example.com/video.mp4",
        }
        self.assertEqual(find_direct_media_url(payload), "")

    def test_finds_media_url_without_a_code_field(self):
        payload = {
            "status": "success",
            "data": {
                "video_url": "https://upos-sz-mirrorcos.bilivideo.com/upgcxcode/video.mp4"
            },
        }
        self.assertEqual(
            find_direct_media_url(payload),
            "https://upos-sz-mirrorcos.bilivideo.com/upgcxcode/video.mp4",
        )


if __name__ == "__main__":
    unittest.main()
