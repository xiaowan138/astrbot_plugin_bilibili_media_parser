from __future__ import annotations

import base64
import html
import io
from datetime import datetime
from typing import Any, Mapping

from .models import (
    ArticleInfo,
    AudioInfo,
    BangumiInfo,
    DynamicInfo,
    LiveInfo,
    VideoInfo,
)


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


def _content_card_context(
    *,
    brand_sub: str,
    content_type: str,
    title: str,
    author_name: str,
    author_meta: str,
    avatar_src: str,
    meta_items: list[tuple[str, str]],
    cover_src: str,
    body_title: str,
    body_text: str,
    tags: list[str],
    stats: list[tuple[str, int]],
    content_id: str,
    canonical_url: str,
    qr_src: str,
    ai_summary: str = "",
    summary_source: str = "",
    gallery_srcs: list[str] | None = None,
    extra_sections: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Shared context builder for article/live/dynamic/bangumi cards."""
    return {
        "brand_sub": _escape(brand_sub),
        "content_type": _escape(content_type),
        "title": _escape(title),
        "author_name": _escape(author_name),
        "author_meta": _escape(author_meta),
        "avatar_src": _escape(avatar_src),
        "meta_items": [
            {"label": _escape(label), "value": _escape(value)}
            for label, value in meta_items
        ],
        "cover_src": _escape(cover_src),
        "gallery_srcs": [_escape(src) for src in (gallery_srcs or []) if src],
        "extra_sections": [
            {"title": _escape(title_text), "text": _escape(text)}
            for title_text, text in (extra_sections or [])
            if text
        ],
        "body_title": _escape(body_title),
        "body_text": _escape(body_text),
        "ai_summary": _escape(_truncate(ai_summary, 700)),
        "summary_source": _escape(summary_source),
        "tags": [_escape(tag) for tag in tags if tag],
        "stats": [
            {"label": _escape(label), "value": format_count(value)}
            for label, value in stats
        ],
        "content_id": _escape(content_id),
        "canonical_url": _escape(canonical_url),
        "qr_src": _escape(qr_src),
        "footer_class": "" if qr_src else "no-qr",
    }


def build_article_card_context(
    article: ArticleInfo,
    *,
    cover_src: str = "",
    avatar_src: str = "",
    qr_src: str = "",
) -> dict[str, Any]:
    published = (
        datetime.fromtimestamp(article.publish_at).strftime("%Y-%m-%d %H:%M")
        if article.publish_at
        else "未知时间"
    )
    summary = _truncate(article.summary, 520) or "作者暂未填写专栏摘要。"
    return _content_card_context(
        brand_sub="B站专栏解析",
        content_type="专栏",
        title=article.title,
        author_name=article.owner_name or "未知作者",
        author_meta=f"UID {article.owner_mid}",
        avatar_src=avatar_src,
        meta_items=[
            ("分类", article.category or "专栏"),
            ("字数", f"{article.words} 字"),
            ("发布", published),
        ],
        cover_src=cover_src,
        body_title="专栏摘要",
        body_text=summary,
        tags=article.tags,
        stats=[
            ("阅读", article.stats.view),
            ("点赞", article.stats.like),
            ("投币", article.stats.coin),
            ("收藏", article.stats.favorite),
            ("评论", article.stats.reply),
            ("分享", article.stats.share),
        ],
        content_id=f"cv{article.article_id}",
        canonical_url=article.canonical_url,
        qr_src=qr_src,
        ai_summary=article.ai_summary,
        summary_source=article.summary_source,
    )


def build_bangumi_card_context(
    bangumi: BangumiInfo,
    *,
    cover_src: str = "",
    avatar_src: str = "",
    qr_src: str = "",
) -> dict[str, Any]:
    meta_items: list[tuple[str, str]] = [
        ("地区", " / ".join(bangumi.area_names) or "未知"),
        ("集数", f"{bangumi.total_episodes} 集"),
    ]
    if bangumi.new_ep_desc:
        meta_items.append(("进度", bangumi.new_ep_desc))
    if bangumi.ep_title:
        meta_items.append(("本集", _truncate(bangumi.ep_title, 24)))
    evaluate = _truncate(bangumi.evaluate, 520) or "暂无剧集简介。"
    extra_sections: list[tuple[str, str]] = []
    if bangumi.episode_names:
        extra_sections.append(("剧集列表", "\n".join(bangumi.episode_names)))
    return _content_card_context(
        brand_sub="B站番剧解析",
        content_type="番剧",
        title=bangumi.title,
        author_name=bangumi.owner_name,
        author_meta=f"UID {bangumi.owner_mid}" if bangumi.owner_mid else "哔哩哔哩",
        avatar_src=avatar_src,
        meta_items=meta_items,
        cover_src=cover_src,
        body_title="剧集简介",
        body_text=evaluate,
        tags=list(bangumi.area_names),
        stats=[
            ("播放", bangumi.view),
            ("追番", bangumi.favorite),
            ("弹幕", bangumi.danmaku),
            ("评论", bangumi.reply),
            ("投币", bangumi.coin),
        ],
        content_id=bangumi.canonical_id,
        canonical_url=bangumi.canonical_url,
        qr_src=qr_src,
        extra_sections=extra_sections,
    )


def build_live_card_context(
    live: LiveInfo,
    *,
    cover_src: str = "",
    avatar_src: str = "",
    qr_src: str = "",
) -> dict[str, Any]:
    status_label = {0: "未开播", 1: "直播中", 2: "轮播中"}.get(
        live.live_status, "未知"
    )
    area = " / ".join(part for part in (live.parent_area_name, live.area_name) if part)
    description = _truncate(live.description, 520) or "主播暂未填写直播简介。"
    tags = [tag.strip() for tag in live.tags.split(",") if tag.strip()]
    return _content_card_context(
        brand_sub="B站直播解析",
        content_type="直播",
        title=live.title or "未命名直播间",
        author_name=live.owner_name or "未知主播",
        author_meta=f"UID {live.owner_mid}",
        avatar_src=avatar_src,
        meta_items=[
            ("分区", area or "直播"),
            ("状态", status_label),
        ],
        cover_src=cover_src,
        body_title="直播简介",
        body_text=description,
        tags=tags,
        stats=[("在线人数", live.online)],
        content_id=f"live{live.room_id}",
        canonical_url=live.canonical_url,
        qr_src=qr_src,
    )


def build_dynamic_card_context(
    dynamic: DynamicInfo,
    *,
    cover_src: str = "",
    avatar_src: str = "",
    qr_src: str = "",
    gallery_srcs: list[str] | None = None,
) -> dict[str, Any]:
    published = (
        datetime.fromtimestamp(dynamic.publish_at).strftime("%Y-%m-%d %H:%M")
        if dynamic.publish_at
        else "未知时间"
    )
    content = _truncate(dynamic.content, 700) or "这条动态没有文字内容。"
    return _content_card_context(
        brand_sub="B站动态解析",
        content_type="动态",
        title=_truncate(dynamic.content, 40) or "动态内容",
        author_name=dynamic.author_name,
        author_meta=f"UID {dynamic.author_mid}",
        avatar_src=avatar_src,
        meta_items=[("发布", published)],
        cover_src=cover_src,
        body_title="动态内容",
        body_text=content,
        tags=[],
        stats=[
            ("点赞", dynamic.like_count),
            ("评论", dynamic.comment_count),
            ("转发", dynamic.forward_count),
            ("收藏", dynamic.favorite_count),
        ],
        content_id=f"opus{dynamic.dyn_id}",
        canonical_url=dynamic.canonical_url,
        qr_src=qr_src,
        ai_summary=dynamic.ai_summary,
        summary_source=dynamic.summary_source,
        gallery_srcs=gallery_srcs,
    )


def build_article_text_fallback(article: ArticleInfo) -> str:
    stats = article.stats
    lines = [
        f"【B站专栏】{article.title}",
        f"作者：{article.owner_name}  |  字数：{article.words}",
        (
            f"阅读 {format_count(stats.view)}  点赞 {format_count(stats.like)}  "
            f"评论 {format_count(stats.reply)}"
        ),
    ]
    if article.summary:
        lines.extend(["摘要：", _truncate(article.summary, 360)])
    if article.ai_summary:
        lines.extend(
            [f"AI概要（{article.summary_source}）：", _truncate(article.ai_summary, 700)]
        )
    return "\n".join(lines)


def build_live_text_fallback(live: LiveInfo) -> str:
    status_label = {0: "未开播", 1: "直播中", 2: "轮播中"}.get(
        live.live_status, "未知"
    )
    lines = [
        f"【B站直播】{live.title or '未命名直播间'}",
        (
            f"主播：{live.owner_name or '未知'}  |  状态：{status_label}  |  "
            f"在线：{format_count(live.online)}"
        ),
    ]
    if live.description:
        lines.extend(["简介：", _truncate(live.description, 360)])
    return "\n".join(lines)


def build_dynamic_text_fallback(dynamic: DynamicInfo) -> str:
    lines = [
        f"【B站动态】{dynamic.author_name}",
        _truncate(dynamic.content, 500) or "这条动态没有文字内容。",
        (
            f"点赞 {format_count(dynamic.like_count)}  "
            f"评论 {format_count(dynamic.comment_count)}  "
            f"转发 {format_count(dynamic.forward_count)}"
        ),
    ]
    if dynamic.ai_summary:
        lines.extend(
            [
                f"AI概要（{dynamic.summary_source}）：",
                _truncate(dynamic.ai_summary, 700),
            ]
        )
    return "\n".join(lines)


def build_bangumi_text_fallback(bangumi: BangumiInfo) -> str:
    lines = [
        f"【B站番剧】{bangumi.title}",
        (
            f"地区：{' / '.join(bangumi.area_names) or '未知'}  |  "
            f"集数：{bangumi.total_episodes}"
        ),
    ]
    if bangumi.ep_title:
        lines.append(f"本集：{bangumi.ep_title}")
    if bangumi.new_ep_desc:
        lines.append(f"进度：{bangumi.new_ep_desc}")
    lines.append(
        f"播放 {format_count(bangumi.view)}  追番 {format_count(bangumi.favorite)}"
    )
    if bangumi.evaluate:
        lines.extend(["简介：", _truncate(bangumi.evaluate, 360)])
    lines.append(bangumi.canonical_url)
    return "\n".join(lines)
