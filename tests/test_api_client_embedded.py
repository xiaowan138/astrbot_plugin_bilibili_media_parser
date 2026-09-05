import asyncio
import unittest

from bilibili_parser.api_client import (
    BilibiliApiClient,
    _embedded_reference,
    _extract_initial_state,
    _extract_meta_urls,
    audio_play_urls_from_payload,
)
from bilibili_parser.extractor import VideoReference


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

    def test_embedded_reference_accepts_live_og_url(self):
        # A live landing page announces itself via og:url; the old filter
        # only accepted bvid/aid and fell through to a whole-page BV scan.
        body = (
            '<meta property="og:url" content="https://live.bilibili.com/12345">'
            '<a href="https://www.bilibili.com/video/BV1zz0000000">相关推荐</a>'
        )
        reference = _embedded_reference(body)
        self.assertIsNotNone(reference)
        self.assertEqual((reference.kind, reference.value), ("live", "12345"))


class _FakeResponse:
    def __init__(self, status, headers=None):
        self.status = status
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeRedirectSession:
    """Responds to every GET with a 302 to the configured location."""

    closed = False

    def __init__(self, location):
        self.location = location
        self.requested = []

    def get(self, url, **kwargs):
        self.requested.append(url)
        return _FakeResponse(302, {"Location": self.location})


class ResolveReferenceRedirectTests(unittest.TestCase):
    def _resolve(self, location):
        client = BilibiliApiClient()
        client._session = _FakeRedirectSession(location)
        reference = VideoReference("url", "https://b23.tv/AbCd12")
        return asyncio.run(client.resolve_reference(reference))

    def test_short_link_to_live_room_resolves_to_live_kind(self):
        resolved = self._resolve("https://live.bilibili.com/12345?share_medium=qq")
        self.assertEqual((resolved.kind, resolved.value), ("live", "12345"))

    def test_short_link_to_dynamic_resolves_to_dynamic_kind(self):
        resolved = self._resolve(
            "https://www.bilibili.com/opus/967717348014293017?x=1"
        )
        self.assertEqual(
            (resolved.kind, resolved.value), ("dynamic", "967717348014293017")
        )

    def test_short_link_to_article_resolves_to_article_kind(self):
        resolved = self._resolve("https://www.bilibili.com/read/cv300010")
        self.assertEqual((resolved.kind, resolved.value), ("article", "300010"))

    def test_short_link_to_audio_resolves_to_auid_kind(self):
        resolved = self._resolve(
            "https://www.bilibili.com/audio/au10004684671"
        )
        self.assertEqual(
            (resolved.kind, resolved.value), ("auid", "10004684671")
        )


if __name__ == "__main__":
    unittest.main()
