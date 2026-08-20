from __future__ import annotations

import base64
import html
import io
from datetime import datetime
from typing import Any, Mapping

from .models import AudioInfo, VideoInfo


def format_count(value: int) -> str:
    value = max(int(value or 0), 0)
    if value < 10_000:
        return str(value)
    if value < 100_000_000:
        number = value / 10_000
        rendered = f"{number:.1f}".rstrip("0").rstrip(".")
        return f"{rendered}万"
    number = value / 100_000_000
    rendered = f"{number:.1f}".rstrip("0").rstrip(".")
    return f"{rendered}亿"


def format_duration(seconds: int) -> str:
    seconds = max(int(seconds or 0), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _truncate(value: str, length: int) -> str:
    normalized = "\n".join(line.strip() for line in value.strip().splitlines())
    if len(normalized) <= length:
        return normalized
    return normalized[: max(length - 1, 0)].rstrip() + "…"


def build_card_context(
    video: VideoInfo,
    *,
    cover_src: str = "",
    avatar_src: str = "",
    comment_avatar_srcs: Mapping[str, str] | None = None,
    qr_src: str = "",
) -> dict[str, Any]:
    published = (
        datetime.fromtimestamp(video.published_at).strftime("%Y-%m-%d %H:%M")
        if video.published_at
        else "未知时间"
    )
    stats = video.stats
    description = _truncate(video.description, 520) or "UP 主暂未填写视频简介。"
    summary = _truncate(video.summary, 700)
    comment_avatar_srcs = comment_avatar_srcs or {}
    comment_contexts = []
    for comment in video.featured_comments:
        replies = [
            {
                "author_name": _escape(_truncate(reply.author_name, 42)),
                "author_initial": _escape(reply.author_name[:1] or "评"),
                "avatar_src": _escape(comment_avatar_srcs.get(reply.author_face_url, "")),
                "content": _escape(_truncate(reply.content, 180)),
                "like_count": format_count(reply.like_count),
            }
            for reply in comment.replies
        ]
        comment_contexts.append(
            {
                "author_name": _escape(_truncate(comment.author_name, 48)),
                "author_initial": _escape(comment.author_name[:1] or "评"),
                "avatar_src": _escape(
                    comment_avatar_srcs.get(comment.author_face_url, "")
                ),
                "content": _escape(_truncate(comment.content, 320)),
                "like_count": format_count(comment.like_count),
                "replies": replies,
            }
        )
    return {
        "title": _escape(video.title),
        "description": _escape(description),
        "cover_src": _escape(cover_src),
        "avatar_src": _escape(avatar_src),
        "owner_name": _escape(video.owner_name),
        "owner_mid": str(video.owner_mid),
        "bvid": _escape(video.bvid),
        "category": _escape(video.category or "视频"),
        "published_at": published,
        "duration": format_duration(video.duration),
        "page_count": str(video.page_count),
        "summary": _escape(summary),
        "summary_source": _escape(video.summary_source),
        "canonical_url": _escape(video.canonical_url),
        "qr_src": _escape(qr_src),
        "footer_class": "" if qr_src else "no-qr",
        "featured_comments": comment_contexts,
        "stats": [
            {"label": "播放", "value": format_count(stats.view)},
            {"label": "弹幕", "value": format_count(stats.danmaku)},
            {"label": "点赞", "value": format_count(stats.like)},
            {"label": "投币", "value": format_count(stats.coin)},
            {"label": "收藏", "value": format_count(stats.favorite)},
            {"label": "评论", "value": format_count(stats.reply)},
            {"label": "分享", "value": format_count(stats.share)},
        ],
    }


def build_text_fallback(video: VideoInfo) -> str:
    stats = video.stats
    lines = [
        f"【B站视频】{video.title}",
        f"UP主：{video.owner_name}  |  时长：{format_duration(video.duration)}",
        (
            f"播放 {format_count(stats.view)}  点赞 {format_count(stats.like)}  "
            f"投币 {format_count(stats.coin)}  收藏 {format_count(stats.favorite)}"
        ),
    ]
    if video.summary:
        lines.extend([f"AI概要（{video.summary_source}）：", _truncate(video.summary, 700)])
    elif video.description:
        lines.extend(["简介：", _truncate(video.description, 360)])
    for comment in video.featured_comments:
        lines.extend([f"前排评论 · {comment.author_name}：", _truncate(comment.content, 240)])
        for reply in comment.replies:
            lines.append(f"回复 · {reply.author_name}：{_truncate(reply.content, 160)}")
    return "\n".join(lines)


def make_qr_data_uri(text: str) -> str:
    try:
        import qrcode

        qr = qrcode.QRCode(version=None, box_size=6, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        image = qr.make_image(fill_color="#111111", back_color="#ffffff")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    except Exception:
        return ""
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_audio_card_context(
    audio: AudioInfo,
    *,
    cover_src: str = "",
    avatar_src: str = "",
    qr_src: str = "",
) -> dict[str, Any]:
    description = _truncate(audio.description, 520) or "作者暂未填写简介。"
    return {
        "title": _escape(audio.title),
        "author": _escape(audio.author or "未知作者"),
        "description": _escape(description),
        "cover_src": _escape(cover_src),
        "avatar_src": _escape(avatar_src),
        "owner_name": _escape(audio.owner_name or "未知 UP 主"),
        "owner_mid": str(audio.owner_mid),
        "au_id": f"au{audio.au_id}",
        "duration": format_duration(audio.duration),
        "canonical_url": _escape(audio.canonical_url),
        "qr_src": _escape(qr_src),
        "footer_class": "" if qr_src else "no-qr",
        "stats": [
            {"label": "播放", "value": format_count(audio.play_count)},
            {"label": "收藏", "value": format_count(audio.collect_count)},
            {"label": "评论", "value": format_count(audio.comment_count)},
        ],
    }


def build_audio_text_fallback(audio: AudioInfo) -> str:
    lines = [
        f"【B站音频】{audio.title}",
        f"作者：{audio.author or '未知'}  |  时长：{format_duration(audio.duration)}",
        (
            f"播放 {format_count(audio.play_count)}  "
            f"收藏 {format_count(audio.collect_count)}  "
            f"评论 {format_count(audio.comment_count)}"
        ),
    ]
    if audio.description:
        lines.extend(["简介：", _truncate(audio.description, 360)])
    if audio.owner_name:
        lines.append(f"上传者：{audio.owner_name}")
    return "\n".join(lines)
