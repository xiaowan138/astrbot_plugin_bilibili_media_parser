"""Pure command parsing helpers for chat commands.

Kept free of AstrBot imports so the behavior can be unit tested directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .extractor import extract_video_reference


@dataclass(frozen=True, slots=True)
class DownloadCommand:
    code: str
    page: int = 1
    media_type: str = "video"


def parse_download_command(
    message: str,
    *,
    video_keyword: str,
    audio_keyword: str,
    video_enabled: bool,
    audio_enabled: bool,
) -> DownloadCommand | None:
    """Parse "视频下载 8978 P2" / "音频下载 482731" style commands."""
    value = str(message or "")
    candidates: list[tuple[str, str]] = []
    if video_enabled and video_keyword:
        candidates.append((video_keyword, "video"))
    if audio_enabled and audio_keyword:
        candidates.append((audio_keyword, "audio"))
    for keyword, media_type in candidates:
        if media_type == "audio":
            pattern = rf"{re.escape(keyword)} ([0-9]+)"
        else:
            pattern = rf"{re.escape(keyword)} ([0-9]+)(?: [Pp]([1-9][0-9]*))?"
        match = re.fullmatch(pattern, value)
        if not match:
            continue
        # 音频命令的正则只有一个捕获组，直接取 group(2) 会抛 IndexError。
        page_group = match.group(2) if (match.lastindex or 0) >= 2 else None
        page = int(page_group) if page_group else 1
        return DownloadCommand(match.group(1), page, media_type=media_type)
    return None


_STATUS_WORDS = ("状态", "查看", "查询")


def is_download_status_command(message: str, keywords: list[str]) -> bool:
    value = str(message or "")
    return any(
        value in {f"{keyword} {word}", f"{keyword}{word}"}
        for keyword in keywords
        for word in _STATUS_WORDS
    )


def is_download_cancel_command(message: str, keywords: list[str]) -> bool:
    value = str(message or "")
    return any(
        value in {f"{keyword} 取消", f"{keyword}取消"} for keyword in keywords
    )


def live_room_id_from_target(target: str) -> int | None:
    """Accept a bare room id or any link that resolves to a live room."""
    text = str(target or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    reference = extract_video_reference(text)
    if reference is not None and reference.kind == "live":
        try:
            return int(reference.value)
        except ValueError:
            return None
    return None


def parse_live_query_command(
    message: str, keyword: str
) -> tuple[bool, int | None]:
    """Return (matched, room_id).

    matched=True with room_id=None means the user sent the bare keyword and
    should receive a usage hint instead of silence.
    """
    if not keyword:
        return False, None
    text = str(message or "").strip()
    if not text:
        return False, None
    if text == keyword:
        return True, None
    match = re.fullmatch(rf"{re.escape(keyword)}\s+(.+)", text)
    if not match:
        return False, None
    return True, live_room_id_from_target(match.group(1))


def parse_live_monitor_command(
    message: str, keyword: str
) -> tuple[str, int | None] | None:
    """Parse "开播提醒 订阅/取消/列表/取消全部" style commands."""
    if not keyword:
        return None
    value = str(message or "").strip()
    if not value or not value.startswith(keyword):
        return None
    rest = value[len(keyword):].strip()
    if not rest or rest in {"帮助", "help", "Help"}:
        return "help", None
    if rest in {"列表", "查看", "状态"}:
        return "list", None
    if rest in {"取消全部", "全部取消", "清空"}:
        return "clear", None
    if rest.startswith("订阅"):
        room_id = live_room_id_from_target(rest[2:].strip())
        if room_id is not None:
            return "subscribe", room_id
    if rest.startswith("取消"):
        room_id = live_room_id_from_target(rest[2:].strip())
        if room_id is not None:
            return "unsubscribe", room_id
    return "help", None


def parse_summary_command(message: str, keyword: str) -> str | None:
    """Parse "视频总结 BV1xx411c7RD" style commands.

    Returns None when the message is not this command, and "" when the user
    sent the bare keyword (caller should show a usage hint).
    """
    if not keyword:
        return None
    value = str(message or "").strip()
    if not value:
        return None
    if value == keyword:
        return ""
    match = re.fullmatch(rf"{re.escape(keyword)}\s+(.+)", value, re.S)
    if not match:
        return None
    return match.group(1).strip()
