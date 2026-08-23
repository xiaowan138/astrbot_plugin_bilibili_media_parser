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
class ArticleStats:
    view: int = 0
    like: int = 0
    coin: int = 0
    favorite: int = 0
    reply: int = 0
    share: int = 0


@dataclass(slots=True)
class ArticleInfo:
    article_id: int
    title: str
    summary: str
    cover_url: str
    category: str
    owner_name: str
    owner_mid: int
    owner_face_url: str
    publish_at: int
    words: int
    stats: ArticleStats = field(default_factory=ArticleStats)
    tags: list[str] = field(default_factory=list)

    @property
    def canonical_url(self) -> str:
        return f"https://www.bilibili.com/read/cv{self.article_id}"

    @property
    def canonical_id(self) -> str:
        return f"cv{self.article_id}"


def article_from_api_data(data: dict[str, Any]) -> ArticleInfo:
    """Convert Bilibili's article API payload into a stable internal model."""
    if not isinstance(data, dict):
        raise ValueError("专栏数据格式无效")

    article_id = _as_int(data.get("id"))
    title = _as_str(data.get("title"))
    if not article_id or not title:
        raise ValueError("专栏数据缺少 id 或标题")

    author = data.get("author") if isinstance(data.get("author"), dict) else {}
    stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
    category = data.get("category") if isinstance(data.get("category"), dict) else {}
    image_urls = data.get("image_urls") if isinstance(data.get("image_urls"), list) else []
    tags = data.get("tags") if isinstance(data.get("tags"), list) else []
    return ArticleInfo(
        article_id=article_id,
        title=title,
        summary=_as_str(data.get("summary")),
        cover_url=_as_str(data.get("banner_url") or (image_urls[0] if image_urls else "")),
        category=_as_str(category.get("name")),
        owner_name=_as_str(author.get("name")) or "未知作者",
        owner_mid=_as_int(author.get("mid")),
        owner_face_url=_as_str(author.get("face")),
        publish_at=_as_int(data.get("publish_time") or data.get("ctime")),
        words=_as_int(data.get("words")),
        stats=ArticleStats(
            view=_as_int(stats.get("view")),
            like=_as_int(stats.get("like")),
            coin=_as_int(stats.get("coin")),
            favorite=_as_int(stats.get("favorite")),
            reply=_as_int(stats.get("reply")),
            share=_as_int(stats.get("share")),
        ),
        tags=[_as_str(tag.get("name")) for tag in tags if isinstance(tag, dict)],
    )


@dataclass(slots=True)
class LiveInfo:
    room_id: int
    title: str
    owner_name: str
    owner_mid: int
    cover_url: str
    online: int
    live_status: int
    parent_area_name: str
    area_name: str
    description: str
    tags: str
    short_id: int = 0

    @property
    def canonical_url(self) -> str:
        return f"https://live.bilibili.com/{self.room_id}"

    @property
    def canonical_id(self) -> str:
        return f"live{self.room_id}"


def live_from_api_data(data: dict[str, Any]) -> LiveInfo:
    """Convert Bilibili's live room API payload into a stable internal model."""
    if not isinstance(data, dict):
        raise ValueError("直播数据格式无效")

    room_id = _as_int(data.get("room_id"))
    if not room_id:
        raise ValueError("直播数据缺少 room_id")

    return LiveInfo(
        room_id=room_id,
        title=_as_str(data.get("title")),
        owner_name=_as_str(data.get("user_name") or data.get("anchor_name")),
        owner_mid=_as_int(data.get("uid")),
        cover_url=_as_str(data.get("user_cover") or data.get("background")),
        online=_as_int(data.get("online")),
        live_status=_as_int(data.get("live_status")),
        parent_area_name=_as_str(data.get("parent_area_name")),
        area_name=_as_str(data.get("area_name")),
        description=_as_str(data.get("description")),
        tags=_as_str(data.get("tags")),
        short_id=_as_int(data.get("short_id")),
    )


@dataclass(slots=True)
class DynamicInfo:
    dyn_id: str
    author_name: str
    author_mid: int
    author_face_url: str
    content: str
    images: list[str] = field(default_factory=list)
    publish_at: int = 0
    like_count: int = 0
    comment_count: int = 0
    forward_count: int = 0
    favorite_count: int = 0

    @property
    def canonical_url(self) -> str:
        return f"https://www.bilibili.com/opus/{self.dyn_id}"

    @property
    def canonical_id(self) -> str:
        return f"opus{self.dyn_id}"


def dynamic_from_page_state(state: dict[str, Any]) -> DynamicInfo:
    """Convert the opus page __INITIAL_STATE__ payload into a DynamicInfo."""
    if not isinstance(state, dict):
        raise ValueError("动态数据格式无效")

    dyn_id = _as_str(state.get("id"))
    detail = state.get("detail") if isinstance(state.get("detail"), dict) else {}
    if not dyn_id:
        raise ValueError("动态数据缺少 id")

    modules = detail.get("modules") if isinstance(detail.get("modules"), list) else []
    author_name = ""
    author_mid = 0
    author_face_url = ""
    publish_at = 0
    content = ""
    images: list[str] = []
    like_count = 0
    comment_count = 0
    forward_count = 0
    favorite_count = 0
    for module in modules:
        if not isinstance(module, dict):
            continue
        module_type = module.get("module_type")
        if module_type == "MODULE_TYPE_AUTHOR":
            author = module.get("module_author")
            if isinstance(author, dict):
                author_name = _as_str(author.get("name"))
                author_mid = _as_int(author.get("mid"))
                author_face_url = _as_str(author.get("face"))
                publish_at = _as_int(author.get("pub_ts"))
        elif module_type == "MODULE_TYPE_CONTENT":
            content_module = module.get("module_content")
            if isinstance(content_module, dict):
                content = _dynamic_content_text(content_module)
        elif module_type == "MODULE_TYPE_STAT":
            stat = module.get("module_stat")
            if isinstance(stat, dict):
                like_count = _as_int((stat.get("like") or {}).get("count"))
                comment_count = _as_int((stat.get("comment") or {}).get("count"))
                forward_count = _as_int((stat.get("forward") or {}).get("count"))
                favorite_count = _as_int((stat.get("favorite") or {}).get("count"))
        elif module_type == "MODULE_TYPE_TOP":
            top = module.get("module_top")
            if isinstance(top, dict):
                display = top.get("display")
                if isinstance(display, dict):
                    album = display.get("album")
                    if isinstance(album, dict):
                        pics = album.get("pics") if isinstance(album.get("pics"), list) else []
                        images = [
                            _as_str(pic.get("url"))
                            for pic in pics
                            if isinstance(pic, dict) and pic.get("url")
                        ]
    return DynamicInfo(
        dyn_id=dyn_id,
        author_name=author_name or "B站用户",
        author_mid=author_mid,
        author_face_url=author_face_url,
        content=content,
        images=images,
        publish_at=publish_at,
        like_count=like_count,
        comment_count=comment_count,
        forward_count=forward_count,
        favorite_count=favorite_count,
    )


def _dynamic_content_text(content_module: dict[str, Any]) -> str:
    """Extract plain text from the dynamic content module paragraphs."""
    paragraphs = (
        content_module.get("paragraphs")
        if isinstance(content_module.get("paragraphs"), list)
        else []
    )
    lines: list[str] = []
    for para in paragraphs:
        if not isinstance(para, dict):
            continue
        text = para.get("text")
        if not isinstance(text, dict):
            continue
        nodes = text.get("nodes") if isinstance(text.get("nodes"), list) else []
        parts: list[str] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("type") == "TEXT_NODE_TYPE_WORD":
                word = node.get("word")
                if isinstance(word, dict):
                    parts.append(_as_str(word.get("words")))
            else:
                rich = node.get("rich")
                if isinstance(rich, dict):
                    parts.append(
                        _as_str(rich.get("text") or rich.get("rich_text"))
                    )
                user = node.get("user")
                if isinstance(user, dict):
                    parts.append(_as_str(user.get("uname")))
        if parts:
            lines.append("".join(part for part in parts if part))
    return "\n".join(lines)


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
