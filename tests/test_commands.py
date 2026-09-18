import unittest

from bilibili_parser.commands import (
    DownloadCommand,
    is_download_cancel_command,
    is_download_status_command,
    live_room_id_from_target,
    parse_download_command,
    parse_live_monitor_command,
    parse_live_query_command,
)

VIDEO = "视频下载"
AUDIO = "音频下载"


def parse(message: str, *, video=True, audio=True):
    return parse_download_command(
        message,
        video_keyword=VIDEO,
        audio_keyword=AUDIO,
        video_enabled=video,
        audio_enabled=audio,
    )


class ParseDownloadCommandTests(unittest.TestCase):
    def test_video_command_without_page(self):
        command = parse("视频下载 482731")
        self.assertEqual(command, DownloadCommand("482731", 1, media_type="video"))

    def test_video_command_with_page(self):
        command = parse("视频下载 482731 P3")
        self.assertEqual(command, DownloadCommand("482731", 3, media_type="video"))

    def test_video_command_with_lowercase_page(self):
        command = parse("视频下载 482731 p12")
        self.assertEqual(command, DownloadCommand("482731", 12, media_type="video"))

    def test_audio_command_does_not_raise_index_error(self):
        # 回归：音频命令正则只有一个捕获组，旧实现取 group(2) 会抛 IndexError。
        command = parse("音频下载 10004684671")
        self.assertEqual(
            command, DownloadCommand("10004684671", 1, media_type="audio")
        )

    def test_audio_command_ignores_page_suffix(self):
        self.assertIsNone(parse("音频下载 10004684671 P2"))

    def test_disabled_media_types_are_not_matched(self):
        self.assertIsNone(parse("视频下载 482731", video=False))
        self.assertIsNone(parse("音频下载 10004684671", audio=False))

    def test_unrelated_text_is_not_matched(self):
        for message in ("", "视频下载", "视频下载 abc", "视频下载 12 P0", "视频下载 12 P3 多余"):
            self.assertIsNone(parse(message))

    def test_empty_keyword_is_not_matched(self):
        command = parse_download_command(
            "视频下载 482731",
            video_keyword="",
            audio_keyword="",
            video_enabled=True,
            audio_enabled=True,
        )
        self.assertIsNone(command)


class DownloadStatusCommandTests(unittest.TestCase):
    def test_accepts_spaced_and_unspaced_forms(self):
        for word in ("状态", "查看", "查询"):
            self.assertTrue(is_download_status_command(f"视频下载 {word}", [VIDEO]))
            self.assertTrue(is_download_status_command(f"视频下载{word}", [VIDEO]))

    def test_rejects_other_text(self):
        self.assertFalse(is_download_status_command("视频下载 482731", [VIDEO]))
        self.assertFalse(is_download_status_command("视频下载 取消", [VIDEO]))
        self.assertFalse(is_download_status_command("状态", []))


class DownloadCancelCommandTests(unittest.TestCase):
    def test_accepts_spaced_and_unspaced_forms(self):
        # 回归：旧实现只识别“视频下载 取消”，不识别无空格的“视频下载取消”。
        self.assertTrue(is_download_cancel_command("视频下载 取消", [VIDEO]))
        self.assertTrue(is_download_cancel_command("视频下载取消", [VIDEO]))
        self.assertTrue(is_download_cancel_command("音频下载取消", [VIDEO, AUDIO]))

    def test_rejects_other_text(self):
        self.assertFalse(is_download_cancel_command("视频下载 取消全部", [VIDEO]))
        self.assertFalse(is_download_cancel_command("取消", [VIDEO]))


class LiveRoomIdFromTargetTests(unittest.TestCase):
    def test_bare_room_id(self):
        self.assertEqual(live_room_id_from_target("21452505"), 21452505)

    def test_live_link(self):
        self.assertEqual(
            live_room_id_from_target("https://live.bilibili.com/21452505"), 21452505
        )

    def test_non_live_target_is_rejected(self):
        self.assertIsNone(live_room_id_from_target(""))
        self.assertIsNone(live_room_id_from_target("不是房间号"))
        self.assertIsNone(
            live_room_id_from_target("https://www.bilibili.com/video/BV1xx411c7mD")
        )


class ParseLiveQueryCommandTests(unittest.TestCase):
    def test_bare_keyword_returns_usage_hint_marker(self):
        self.assertEqual(parse_live_query_command("直播查询", "直播查询"), (True, None))

    def test_room_id_target(self):
        self.assertEqual(
            parse_live_query_command("直播查询 21452505", "直播查询"),
            (True, 21452505),
        )

    def test_link_target(self):
        self.assertEqual(
            parse_live_query_command(
                "直播查询 https://live.bilibili.com/21452505", "直播查询"
            ),
            (True, 21452505),
        )

    def test_invalid_target_still_matches(self):
        # 命令本身匹配，但目标解析不出房间号：返回 (True, None) 之外的失败形式。
        matched, room_id = parse_live_query_command("直播查询 abc", "直播查询")
        self.assertTrue(matched)
        self.assertIsNone(room_id)

    def test_unrelated_message_does_not_match(self):
        self.assertEqual(parse_live_query_command("随便聊聊", "直播查询"), (False, None))

    def test_empty_keyword_disables_the_command(self):
        self.assertEqual(parse_live_query_command("直播查询 6", ""), (False, None))


class ParseLiveMonitorCommandTests(unittest.TestCase):
    def test_bare_keyword_is_help(self):
        self.assertEqual(parse_live_monitor_command("开播提醒", "开播提醒"), ("help", None))

    def test_subscribe_with_room_id(self):
        self.assertEqual(
            parse_live_monitor_command("开播提醒 订阅 21452505", "开播提醒"),
            ("subscribe", 21452505),
        )

    def test_subscribe_with_link(self):
        self.assertEqual(
            parse_live_monitor_command(
                "开播提醒 订阅 https://live.bilibili.com/21452505", "开播提醒"
            ),
            ("subscribe", 21452505),
        )

    def test_unsubscribe(self):
        self.assertEqual(
            parse_live_monitor_command("开播提醒 取消 21452505", "开播提醒"),
            ("unsubscribe", 21452505),
        )

    def test_clear_all(self):
        for text in ("开播提醒 取消全部", "开播提醒 全部取消", "开播提醒 清空"):
            self.assertEqual(parse_live_monitor_command(text, "开播提醒"), ("clear", None))

    def test_list(self):
        for text in ("开播提醒 列表", "开播提醒 查看", "开播提醒 状态"):
            self.assertEqual(parse_live_monitor_command(text, "开播提醒"), ("list", None))

    def test_invalid_target_falls_back_to_help(self):
        self.assertEqual(
            parse_live_monitor_command("开播提醒 订阅 abc", "开播提醒"), ("help", None)
        )

    def test_unrelated_message_does_not_match(self):
        self.assertIsNone(parse_live_monitor_command("提醒我一下", "开播提醒"))

    def test_empty_keyword_disables_the_command(self):
        self.assertIsNone(parse_live_monitor_command("开播提醒 订阅 6", ""))


if __name__ == "__main__":
    unittest.main()
