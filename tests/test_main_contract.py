import ast
import unittest
from pathlib import Path


class MainHandlerContractTests(unittest.TestCase):
    def test_event_is_stopped_only_after_all_yielded_results(self):
        source_path = Path(__file__).parents[1] / "main.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        handler = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "on_message"
        )
        yield_lines = [
            node.lineno for node in ast.walk(handler) if isinstance(node, ast.Yield)
        ]
        stop_lines = [
            node.lineno
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "stop_event"
        ]

        self.assertTrue(yield_lines)
        self.assertEqual(len(stop_lines), 1)
        self.assertGreater(stop_lines[0], max(yield_lines))

    def test_handler_sends_the_canonical_bilibili_link(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("B站视频源链接：", source)
        self.assertIn("video.canonical_url", source)
        self.assertIn("Comp.Image.fromFileSystem(image_path)", source)
        self.assertIn("Comp.Plain", source)
        self.assertIn('f"B站视频源链接：', source)
        self.assertNotIn('f"\\nB站视频源链接：', source)
        self.assertIn("f\"B站视频源链接：\\n{video.canonical_url}{download_hint}\"", source)
        self.assertNotIn('yield event.plain_result(\n                        "需要视频文件时', source)

    def test_video_download_is_keyword_gated_and_uses_temporary_file(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("download_command = self._parse_download_command(event.message_str)", source)
        self.assertIn("re.fullmatch(", source)
        self.assertIn("secrets.compare_digest(command.code, pending.code)", source)
        self.assertIn("secrets.randbelow", source)
        self.assertIn("video_download_max_concurrency", source)
        self.assertIn('"video_download_max_queue", 10, 0, 100', source)
        self.assertIn("_prune_download_state(now, ttl, cooldown)", source)
        self.assertIn("当前下载队列已满，请稍后再试。", source)
        self.assertIn("_is_download_status_command", source)
        self.assertIn('f"{keyword} 查看"', source)
        self.assertIn("可查看下载进度", source)
        self.assertIn("_is_download_cancel_command", source)
        self.assertIn('"video_download_max_duration_seconds", 900, 0, 14400', source)
        self.assertIn("视频下载已拒绝：视频时长", source)
        self.assertIn("Comp.Video.fromBase64(video_base64)", source)
        self.assertNotIn('Comp.Plain(f"B站视频源链接：\\n{video.canonical_url}")', source)
        self.assertIn("tempfile.mkdtemp", source)
        self.assertIn("base64.b64encode(video_file.read()).decode", source)
        self.assertIn("shutil.rmtree(download_dir, ignore_errors=True)", source)
        self.assertIn("hide_download_hint_when_unavailable", source)
        self.assertIn("_download_is_ready(event, video)", source)
        self.assertIn("_auto_download_is_ready(event, video)", source)
        self.assertIn("video_download_auto_send", source)
        self.assertIn("def _download_request_allowed", source)
        self.assertIn('yield event.plain_result("正在排队下载视频，请稍候。")', source)
        self.assertNotIn("Comp.Video.fromURL", source)

    def test_event_is_stopped_only_when_the_message_was_handled(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        # The handler must not stop propagation for ordinary messages, otherwise
        # other plugins and the main agent would never see them.
        self.assertIn("handled = False", source)
        self.assertIn("if reference is None:\n                return\n            handled = True", source)
        self.assertIn("if handled:", source)
        self.assertLess(
            source.index("if handled:"), source.index("event.stop_event()")
        )

    def test_download_quota_is_consumed_only_after_validation(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("async def _consume_download_quota", source)
        self.assertIn("await self._consume_download_quota(event)", source)
        self.assertIn("def _finish_download_job(job", source)
        # The semaphore must be released in a single finally to avoid leaks.
        self.assertIn("finally:\n            self._download_semaphore.release()", source)

    def test_transcription_can_be_cancelled_on_terminate(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("_transcription_cancels", source)
        self.assertIn("for cancel_event in self._transcription_cancels:", source)

    def test_short_link_parsing_prefers_structured_metadata(self):
        source_path = Path(__file__).parents[1] / "main.py"
        client_source = (
            Path(__file__).parents[1] / "bilibili_parser" / "api_client.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _embedded_reference", client_source)
        self.assertIn("_extract_meta_urls", client_source)
        self.assertIn("_extract_initial_state", client_source)
        self.assertIn("def _prune_cache", source_path.read_text(encoding="utf-8"))

    def test_ai_summary_prefers_public_subtitles_without_metadata_fallback(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        client_source = (Path(__file__).parents[1] / "bilibili_parser" / "api_client.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"subtitle_page_limit", 3, 0, 20', source)
        self.assertIn("page_limit=subtitle_page_limit", source)
        self.assertIn('"summary_fallback_to_metadata", False', source)
        self.assertIn("视频未提供可用公开字幕，跳过 AI 总结", source)
        self.assertIn("asyncio.gather(", client_source)
        self.assertIn("_fetch_public_subtitle_for_cid", client_source)
        self.assertIn("（中间字幕已省略）", client_source)
        self.assertIn("bilibili_sessdata", source)
        self.assertIn("include_bilibili_cookie=True", client_source)
        self.assertIn('headers = {"Cookie": f"SESSDATA={self._sessdata}"}', client_source)
        self.assertIn("enable_voice_transcription", source)
        self.assertIn("faster_whisper", source)
        self.assertIn("shutil.rmtree(download_dir, ignore_errors=True)", source)


if __name__ == "__main__":
    unittest.main()
