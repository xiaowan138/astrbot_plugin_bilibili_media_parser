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
        self.assertIn("download_command = self._parse_download_command(message_text)", source)
        self.assertIn("return parse_download_command(", source)
        self.assertIn("secrets.compare_digest(command.code, pending.code)", source)
        self.assertIn("secrets.randbelow", source)
        self.assertIn("video_download_max_concurrency", source)
        self.assertIn('"video_download_max_queue", 10, 0, 100', source)
        self.assertIn("_prune_download_state(now, ttl, cooldown)", source)
        self.assertIn("当前下载队列已满，请稍后再试。", source)
        self.assertIn("_is_download_status_command", source)
        self.assertIn("return is_download_status_command(", source)
        self.assertIn("可查看下载进度", source)
        self.assertIn("_is_download_cancel_command", source)
        self.assertIn("return is_download_cancel_command(", source)
        self.assertIn('"video_download_max_duration_seconds", 900, 0, 14400', source)
        self.assertIn("视频下载已拒绝：视频时长", source)
        self.assertIn("Comp.Video.fromBase64(video_base64)", source)
        self.assertNotIn('Comp.Plain(f"B站视频源链接：\\n{video.canonical_url}")', source)
        self.assertIn("tempfile.mkdtemp", source)
        self.assertIn("base64.b64encode(media_file.read()).decode", source)
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
        self.assertIn("if not references:\n                return\n            handled = True", source)
        self.assertIn("if handled:", source)
        self.assertLess(
            source.index("if handled:"), source.index("event.stop_event()")
        )

    def test_multi_link_dispatch_is_bounded(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("extract_video_references(", source)
        self.assertIn('"max_links_per_message", 3, 1, 5', source)
        self.assertIn("for reference in references[:limit]:", source)

    def test_live_monitor_and_query_commands_exist(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("_parse_live_query_command", source)
        self.assertIn("_parse_live_monitor_command", source)
        self.assertIn("_handle_live_monitor_command", source)
        self.assertIn("_ensure_live_monitor_started", source)
        self.assertIn('"enable_live_monitor", False', source)
        self.assertIn('"live_monitor_interval_seconds", 60, 30, 600', source)
        self.assertIn("should_notify_live_start", source)
        self.assertIn("LiveSubscriptionStore", source)
        # 订阅必须持久化，重启后仍生效。
        self.assertIn("StarTools.get_data_dir", source)
        self.assertIn("live_subscriptions.json", source)
        # 终止时要停掉监控任务。
        self.assertIn("self._live_monitor_task.cancel()", source)

    def test_audio_download_shares_the_download_state_machine(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("_audio_download_keyword", source)
        self.assertIn('"enable_audio_download", False', source)
        self.assertIn("_remember_audio_download", source)
        self.assertIn("_handle_audio_download", source)
        self.assertIn("fetch_audio_play_url", source)
        self.assertIn("Comp.Record.fromBase64(audio_base64)", source)
        # 音频下载不需要妖狐 Key，但复用权限/冷却/每日上限等限制。
        self.assertIn("_audio_download_request_allowed", source)
        self.assertIn('"audio_download_keyword", "音频下载"', source)

    def test_content_ai_summary_uses_shared_llm_helper(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("_with_content_ai_summary", source)
        self.assertIn("_request_ai_summary", source)
        self.assertIn('ai_summary=summary, summary_source=source', source)

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

    def test_command_parsing_lives_in_the_pure_module(self):
        commands_source = (
            Path(__file__).parents[1] / "bilibili_parser" / "commands.py"
        ).read_text(encoding="utf-8")
        self.assertIn("re.fullmatch(", commands_source)
        # 音频命令只有一个捕获组，必须先检查 lastindex 再取 group(2)。
        self.assertIn("match.lastindex", commands_source)
        # “视频下载取消”（无空格）也必须识别。
        self.assertIn('f"{keyword}取消"', commands_source)

    def test_download_validation_failures_restore_the_code(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("async def _restore_pending", source)
        self.assertIn("await self._restore_pending(event, pending)", source)

    def test_live_query_uses_a_short_cache(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn('"live_cache_seconds", 60, 0, 3600', source)

    def test_live_end_notify_is_supported(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn('"enable_live_end_notify", False', source)
        self.assertIn("should_notify_live_end", source)
        self.assertIn("async def _notify_live_end", source)

    def test_live_monitor_stops_when_disabled_and_polling_is_limited(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("def _live_monitor_enabled", source)
        self.assertIn("asyncio.Semaphore(5)", source)
        # 取消全部订阅后要清理掉无人订阅房间的状态缓存。
        self.assertIn("for room in list(self._live_status_cache):", source)

    def test_dynamic_gallery_is_wired_into_rendering(self):
        source_path = Path(__file__).parents[1] / "main.py"
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("gallery_srcs=gallery_srcs", source)


if __name__ == "__main__":
    unittest.main()
