import unittest

from bilibili_parser.api_client import (
    _embedded_reference,
    _extract_initial_state,
    _extract_meta_urls,
)


class EmbeddedReferenceTests(unittest.TestCase):
    def test_meta_extractor_collects_og_video_and_og_url(self):
        body = (
            '<meta property="og:video" content="https://www.bilibili.com/video/BV1xx411c7mD">'
            '<meta name="og:url" content="//www.bilibili.com/video/BV1xx411c7mD?p=2">'
            '<meta property="og:title" content="测试">'
        )
        urls = _extract_meta_urls(body, ("og:video", "og:url"))
        self.assertEqual(len(urls), 2)
        self.assertTrue(urls[0].startswith("https://www.bilibili.com"))

    def test_meta_extractor_ignores_other_meta(self):
        body = '<meta property="og:title" content="你好">'
        self.assertEqual(_extract_meta_urls(body, ("og:video", "og:url")), [])

    def test_initial_state_parses_video_data(self):
        body = (
            "<script>window.__INITIAL_STATE__={\"videoData\":{\"bvid\":\"BV1xx411c7mD\","
            '"aid\":170001},"extra":{}};</script>'
        )
        state = _extract_initial_state(body)
        self.assertIsNotNone(state)
        self.assertEqual(state["videoData"]["bvid"], "BV1xx411c7mD")

    def test_initial_state_handles_nested_braces_and_strings(self):
        body = (
            "<script>window.__INITIAL_STATE__={\"videoData\":{\"bvid\":\"BV1xx411c7mD\","
            '"desc\":\"} not a real closing brace\"}};</script>'
        )
        state = _extract_initial_state(body)
        self.assertIsNotNone(state)
        self.assertEqual(state["videoData"]["bvid"], "BV1xx411c7mD")
        self.assertEqual(state["videoData"]["desc"], "} not a real closing brace")

    def test_initial_state_missing_marker(self):
        self.assertIsNone(_extract_initial_state("<html>no state here</html>"))

    def test_embedded_reference_prefers_og_meta_over_related_video_bv(self):
        # The first BV in the page belongs to a related video; the og:video
        # meta names the real target. Structured extraction must win.
        body = (
            '<meta property="og:video" content="https://www.bilibili.com/video/BV1xx411c7mD">'
            '<script>window.__INITIAL_STATE__={"videoData":{"bvid":"BV1yy0000000"}};</script>'
            '<a href="https://www.bilibili.com/video/BV1zz0000000">相关推荐</a>'
        )
        reference = _embedded_reference(body)
        self.assertIsNotNone(reference)
        self.assertEqual(reference.value, "BV1xx411c7mD")

    def test_embedded_reference_falls_back_to_initial_state(self):
        body = (
            "<script>window.__INITIAL_STATE__={\"videoData\":{\"bvid\":\"BV1xx411c7mD\","
            '"aid\":170001}};</script>'
        )
        reference = _embedded_reference(body)
        self.assertIsNotNone(reference)
        self.assertEqual(reference.value, "BV1xx411c7mD")

    def test_embedded_reference_returns_none_when_unrelated(self):
        self.assertIsNone(_embedded_reference("<html>no video here</html>"))


if __name__ == "__main__":
    unittest.main()
