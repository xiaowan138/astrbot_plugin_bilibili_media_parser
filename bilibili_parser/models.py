from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_str(value: Any) -> str:
    return str(value or "").strip()


@dataclass(slots=True)
class VideoStats:
    view: int = 0
    danmaku: int = 0
    reply: int = 0
    favorite: int = 0
    coin: int = 0
    share: int = 0
    like: int = 0


@dataclass(slots=True)
class CommentReply:
    author_name: str
    author_face_url: str
    content: str
    like_count: int = 0


@dataclass(slots=True)
class FeaturedComment:
    author_name: str
    author_face_url: str
    content: str
    like_count: int = 0
    replies: list[CommentReply] = field(default_factory=list)


@dataclass(slots=True)
class VideoPage:
    index: int
    cid: int
    title: str
    duration: int


@dataclass(slots=True)
class AudioInfo:
    au_id: int
    title: str
    author: str
    cover_url: str
    duration: int
    description: str
    owner_name: str
    owner_mid: int
    play_count: int
    collect_count: int
    comment_count: int

    @property
    def canonical_url(self) -> str:
        return f"https://www.bilibili.com/audio/au{self.au_id}"

    @property
    def canonical_id(self) -> str:
        return f"au{self.au_id}"


def audio_from_api_data(data: dict[str, Any]) -> AudioInfo:
    """Convert Bilibili's audio API payload into a stable internal model."""
    if not isinstance(data, dict):
        raise ValueError("音频数据格式无效")

    au_id = _as_int(data.get("id"))
    title = _as_str(data.get("title"))
    if not au_id or not title:
        raise ValueError("音频数据缺少 id 或标题")

    statistic = data.get("statistic") if isinstance(data.get("statistic"), dict) else {}
    return AudioInfo(
        au_id=au_id,
        title=title,
        author=_as_str(data.get("author")),
        cover_url=_as_str(data.get("cover")),
        duration=_as_int(data.get("duration")),
        description=_as_str(data.get("intro") or data.get("description")),
        owner_name=_as_str(data.get("uname")),
        owner_mid=_as_int(data.get("uid")),
        play_count=_as_int(statistic.get("play")),
        collect_count=_as_int(statistic.get("collect")),
        comment_count=_as_int(statistic.get("comment")),
    )


@dataclass(slots=True)
class VideoInfo:
    aid: int
    bvid: str
    cid: int
    title: str
    description: str
    cover_url: str
    duration: int
    published_at: int
    category: str
    owner_name: str
    owner_face_url: str
    owner_mid: int
    page_count: int
    pages: list[VideoPage] = field(default_factory=list)
    stats: VideoStats = field(default_factory=VideoStats)
    featured_comments: list[FeaturedComment] = field(default_factory=list)
    summary: str = ""
    summary_source: str = ""

    @property
    def canonical_url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"

    @property
    def canonical_id(self) -> str:
        return self.bvid or f"av{self.aid}"

    def page_url(self, page: int) -> str:
        return self.canonical_url if page <= 1 else f"{self.canonical_url}?p={page}"


def video_from_view_data(data: dict[str, Any]) -> VideoInfo:
    """Convert Bilibili's view payload into a stable internal model."""
    if not isinstance(data, dict):
        raise ValueError("视频数据格式无效")

    bvid = _as_str(data.get("bvid"))
    aid = _as_int(data.get("aid"))
    title = _as_str(data.get("title"))
    if not bvid or not aid or not title:
        raise ValueError("视频数据缺少 bvid、aid 或标题")

    owner = data.get("owner") if isinstance(data.get("owner"), dict) else {}
    stat = data.get("stat") if isinstance(data.get("stat"), dict) else {}
    pages = data.get("pages") if isinstance(data.get("pages"), list) else []

    cid = _as_int(data.get("cid"))
    if not cid and pages and isinstance(pages[0], dict):
        cid = _as_int(pages[0].get("cid"))

    parsed_pages = [
        VideoPage(
            index=index,
            cid=_as_int(page.get("cid")),
            title=_as_str(page.get("part")),
            duration=_as_int(page.get("duration")),
        )
        for index, page in enumerate(pages, start=1)
        if isinstance(page, dict)
    ]
    return VideoInfo(
        aid=aid,
        bvid=bvid,
        cid=cid,
        title=title,
        description=_as_str(data.get("desc")),
        cover_url=_as_str(data.get("pic")),
        duration=_as_int(data.get("duration")),
        published_at=_as_int(data.get("pubdate") or data.get("ctime")),
        category=_as_str(data.get("tname")),
        owner_name=_as_str(owner.get("name")) or "未知 UP 主",
        owner_face_url=_as_str(owner.get("face")),
        owner_mid=_as_int(owner.get("mid")),
        page_count=max(_as_int(data.get("videos")), len(pages), 1),
        pages=parsed_pages,
        stats=VideoStats(
            view=_as_int(stat.get("view")),
            danmaku=_as_int(stat.get("danmaku")),
            reply=_as_int(stat.get("reply")),
            favorite=_as_int(stat.get("favorite")),
            coin=_as_int(stat.get("coin")),
            share=_as_int(stat.get("share")),
            like=_as_int(stat.get("like")),
        ),
    )
