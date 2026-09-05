from __future__ import annotations

import asyncio
import base64
import json
import logging
import random
import re
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

import aiohttp
from PIL import Image, ImageOps

from .extractor import VideoReference, extract_video_reference
from .models import (
    ArticleInfo,
    AudioInfo,
    BangumiInfo,
    CommentReply,
    DynamicInfo,
    FeaturedComment,
    LiveInfo,
    VideoInfo,
    article_from_api_data,
    audio_from_api_data,
    bangumi_from_api_data,
    dynamic_from_page_state,
    live_from_api_data,
    video_from_view_data,
)
from .yaohud import YAO_HUD_ENDPOINT, find_direct_media_url, is_allowed_media_url


API_BASE = "https://api.bilibili.com"
AUDIO_API_BASE = "https://www.bilibili.com"
LIVE_API_BASE = "https://api.live.bilibili.com"
_SHORT_HOSTS = {"b23.tv", "bili2233.cn", "www.bili2233.cn"}
_PAGE_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com"}
_IMAGE_HOST_SUFFIXES = (".hdslb.com", ".bilibili.com")
_SUBTITLE_HOST_SUFFIXES = (".hdslb.com", ".bilibili.com")

logger = logging.getLogger(__name__)

# 引用类型全集：短链重定向后可能落在任何一种内容上，都必须接受。
_TYPED_KINDS = frozenset(
    {"bvid", "aid", "auid", "article", "live", "dynamic", "ep", "ss"}
)


class BilibiliApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedVideo:
    kind: str
    value: str

    @property
    def canonical_id(self) -> str:
        if self.kind == "bvid":
            return self.value
        if self.kind == "aid":
            return f"av{self.value}"
        if self.kind == "auid":
            return f"au{self.value}"
        if self.kind == "article":
            return f"cv{self.value}"
        if self.kind == "live":
            return f"live{self.value}"
        if self.kind == "dynamic":
            return f"opus{self.value}"
        if self.kind == "ep":
            return f"ep{self.value}"
        if self.kind == "ss":
            return f"ss{self.value}"
        return self.value


_META_TAG_RE = re.compile(
    r"<meta[^>]*\b(?:property|name)=[\"']([^\"']*)[\"'][^>]*>",
    re.I,
)
_META_ATTR_RE = re.compile(r"\b(property|name|content)=[\"']([^\"']*)[\"']", re.I)


def _extract_meta_urls(body: str, names: tuple[str, ...]) -> list[str]:
    """Collect the content of matching <meta property/name> tags."""
    wanted = {name.lower() for name in names}
    urls: list[str] = []
    for tag in _META_TAG_RE.finditer(body):
        attrs = _META_ATTR_RE.findall(tag.group(0))
        # attrs is a list of (attr_name, attr_value) tuples.
        # Pair each wanted name with an adjacent content value.
        for idx, (attr_name, attr_value) in enumerate(attrs):
            if attr_name.lower() == "content":
                continue
            if attr_value.lower() not in wanted:
                continue
            # Look for the nearest content attribute: prefer next, then previous.
            if idx + 1 < len(attrs) and attrs[idx + 1][0].lower() == "content":
                urls.append(attrs[idx + 1][1])
            elif idx > 0 and attrs[idx - 1][0].lower() == "content":
                urls.append(attrs[idx - 1][1])
    return urls


def _extract_initial_state(body: str) -> dict[str, Any] | None:
    """Parse window.__INITIAL_STATE__ JSON with a brace-balance scan."""
    marker = "window.__INITIAL_STATE__"
    position = body.find(marker)
    if position < 0:
        return None
    start = body.find("{", position)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(body)):
        char = body[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    decoded = json.loads(body[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return decoded if isinstance(decoded, dict) else None
    return None


def audio_play_urls_from_payload(payload: Any) -> list[str]:
    """Pull ordered CDN URLs out of the music-service /web/url response."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    cdns = data.get("cdns")
    if not isinstance(cdns, list):
        return []
    return [
        str(url).strip()
        for url in cdns
        if str(url or "").strip()
    ]


def _embedded_reference(body: str) -> VideoReference | None:
    """Prefer structured page metadata over scanning the whole HTML.

    A plain first-BV match on a b23.tv landing page can hit a related
    video in the recommendation feed instead of the shared video.
    """
    for meta_url in _extract_meta_urls(body, ("og:video", "og:url")):
        direct = extract_video_reference(meta_url)
        if direct and direct.kind in _TYPED_KINDS:
            return direct
    initial_state = _extract_initial_state(body)
    if isinstance(initial_state, dict):
        video_data = initial_state.get("videoData")
        if isinstance(video_data, dict):
            bvid = str(video_data.get("bvid") or "").strip()
            if re.fullmatch(r"BV[0-9A-Za-z]{10}", bvid):
                return VideoReference("bvid", bvid)
            aid = str(video_data.get("aid") or "").strip()
            if aid:
                return VideoReference("aid", aid)
    return None


class BilibiliApiClient:
    def __init__(self, timeout_seconds: float = 15, sessdata: str = "") -> None:
        self.timeout_seconds = max(float(timeout_seconds), 3.0)
        self._sessdata = self._normalize_sessdata(sessdata)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
                    ),
                    "Referer": "https://www.bilibili.com/",
                    "Accept": "application/json,text/plain,*/*",
                },
                # AstrBot deployments often provide a proxy for outbound media.
                # Image URLs remain host-restricted before they are requested.
                trust_env=True,
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def resolve_reference(self, reference: VideoReference) -> ResolvedVideo:
        if reference.kind in _TYPED_KINDS:
            return ResolvedVideo(reference.kind, reference.value)

        current = reference.value
        for _ in range(6):
            self._validate_bilibili_url(current)
            direct = extract_video_reference(current)
            if direct and direct.kind in _TYPED_KINDS:
                return ResolvedVideo(direct.kind, direct.value)

            session = await self._get_session()
            try:
                async with session.get(current, allow_redirects=False) as response:
                    if response.status in {301, 302, 303, 307, 308}:
                        location = response.headers.get("Location")
                        if not location:
                            raise BilibiliApiError("B 站短链缺少跳转地址")
                        current = urljoin(current, location)
                        continue
                    if response.status >= 400:
                        raise BilibiliApiError(
                            f"B 站短链请求失败（HTTP {response.status}）"
                        )
                    body = (await response.content.read(200_000)).decode(
                        "utf-8", errors="ignore"
                    )
            except asyncio.TimeoutError as exc:
                raise BilibiliApiError("B 站短链解析超时") from exc
            except aiohttp.ClientError as exc:
                raise BilibiliApiError(f"B 站短链请求失败：{exc}") from exc

            embedded = _embedded_reference(body)
            if embedded is None:
                embedded = extract_video_reference(body)
            if embedded and embedded.kind in _TYPED_KINDS:
                return ResolvedVideo(embedded.kind, embedded.value)
            break

        raise BilibiliApiError("没有从链接中找到有效的 B 站内容编号")

    async def fetch_video_info(self, resolved: ResolvedVideo) -> VideoInfo:
        params = {"bvid": resolved.value} if resolved.kind == "bvid" else {"aid": resolved.value}
        payload = await self._get_api_json("/x/web-interface/view", params)
        try:
            return video_from_view_data(payload)
        except ValueError as exc:
            raise BilibiliApiError(str(exc)) from exc

    async def fetch_audio_info(self, resolved: ResolvedVideo) -> AudioInfo:
        """Fetch Bilibili audio (AU) metadata via the music-service API."""
        if resolved.kind != "auid":
            raise BilibiliApiError(f"内部错误：fetch_audio_info 期望 auid 类型，实际为 {resolved.kind}")
        try:
            au_id = int(resolved.value)
        except (ValueError, TypeError) as exc:
            raise BilibiliApiError(f"音频 AU 号格式无效：{resolved.value}") from exc
        payload = await self._get_api_json(
            "/audio/music-service-c/web/song/info",
            {"sid": au_id},
            base=AUDIO_API_BASE,
        )
        try:
            return audio_from_api_data(payload)
        except ValueError as exc:
            raise BilibiliApiError(str(exc)) from exc

    async def fetch_article_info(self, resolved: ResolvedVideo) -> ArticleInfo:
        """Fetch Bilibili article (CV) metadata via the article API."""
        if resolved.kind != "article":
            raise BilibiliApiError(
                f"内部错误：fetch_article_info 期望 article 类型，实际为 {resolved.kind}"
            )
        try:
            article_id = int(resolved.value)
        except (ValueError, TypeError) as exc:
            raise BilibiliApiError(
                f"专栏 CV 号格式无效：{resolved.value}"
            ) from exc
        payload = await self._get_api_json(
            "/x/article/view",
            {"id": article_id},
        )
        try:
            return article_from_api_data(payload)
        except ValueError as exc:
            raise BilibiliApiError(str(exc)) from exc

    async def fetch_live_info(self, resolved: ResolvedVideo) -> LiveInfo:
        """Fetch Bilibili live room metadata via the live API."""
        if resolved.kind != "live":
            raise BilibiliApiError(
                f"内部错误：fetch_live_info 期望 live 类型，实际为 {resolved.kind}"
            )
        try:
            room_id = int(resolved.value)
        except (ValueError, TypeError) as exc:
            raise BilibiliApiError(f"直播房间号格式无效：{resolved.value}") from exc
        data = await self._get_json_url(
            LIVE_API_BASE + "/room/v1/Room/get_info",
            params={"room_id": room_id},
        )
        if not isinstance(data, dict):
            raise BilibiliApiError("B 站接口返回了无效数据")
        code = data.get("code")
        if code != 0:
            message = str(data.get("message") or data.get("msg") or "未知错误")
            raise BilibiliApiError(f"B 站接口错误 {code}：{message}")
        payload = data.get("data")
        if not isinstance(payload, dict):
            raise BilibiliApiError("B 站接口缺少 data 字段")
        try:
            info = live_from_api_data(payload)
        except ValueError as exc:
            raise BilibiliApiError(str(exc)) from exc
        # The room-info API does not include the anchor name or avatar. When
        # they are missing, resolve both once from the user card by mid.
        if (not info.owner_name or not info.owner_face_url) and info.owner_mid:
            try:
                card = await self._get_api_json(
                    "/x/web-interface/card", {"mid": info.owner_mid}
                )
                card_data = card.get("card") if isinstance(card.get("card"), dict) else {}
                name = str(card_data.get("name") or "").strip()
                face = str(card_data.get("face") or "").strip()
                if name or face:
                    info = replace(info, owner_name=name or info.owner_name,
                                   owner_face_url=face or info.owner_face_url)
            except BilibiliApiError:
                pass
        return info

    async def fetch_dynamic_info(self, resolved: ResolvedVideo) -> DynamicInfo:
        """Fetch Bilibili dynamic (opus) metadata from the server-rendered page."""
        if resolved.kind != "dynamic":
            raise BilibiliApiError(
                f"内部错误：fetch_dynamic_info 期望 dynamic 类型，实际为 {resolved.kind}"
            )
        dyn_id = resolved.value
        if not dyn_id:
            raise BilibiliApiError("动态 ID 为空")
        body = await self._get_page_text(
            f"https://www.bilibili.com/opus/{dyn_id}"
        )
        state = _extract_initial_state(body)
        if state is None:
            raise BilibiliApiError("动态页面缺少数据")
        try:
            return dynamic_from_page_state(state)
        except ValueError as exc:
            raise BilibiliApiError(str(exc)) from exc

    async def fetch_bangumi_info(self, resolved: ResolvedVideo) -> BangumiInfo:
        """Fetch bangumi/season metadata via the pgc season API."""
        if resolved.kind not in {"ep", "ss"}:
            raise BilibiliApiError(
                f"内部错误：fetch_bangumi_info 期望 ep/ss 类型，实际为 {resolved.kind}"
            )
        try:
            numeric_id = int(resolved.value)
        except (ValueError, TypeError) as exc:
            raise BilibiliApiError(f"番剧编号格式无效：{resolved.value}") from exc

        params = (
            {"ep_id": numeric_id}
            if resolved.kind == "ep"
            else {"season_id": numeric_id}
        )
        # pgc 接口的成功载荷放在 result 字段而不是 data 字段。
        payload = await self._get_pgc_json("/pgc/view/web/season", params)
        try:
            return bangumi_from_api_data(
                payload, ep_id=numeric_id if resolved.kind == "ep" else 0
            )
        except ValueError as exc:
            raise BilibiliApiError(str(exc)) from exc

    async def fetch_audio_play_url(self, au_id: int, *, quality: int = 1) -> str:
        """Resolve one trusted audio stream URL for an AU id (no login required)."""
        payload = await self._get_json_url(
            AUDIO_API_BASE + "/audio/music-service-c/web/url",
            params={"sid": au_id, "cdnNum": 3, "quality": quality},
        )
        code = payload.get("code")
        if code != 0:
            message = str(payload.get("msg") or payload.get("message") or "未知错误")
            raise BilibiliApiError(f"B 站音频接口错误 {code}：{message}")
        for candidate in audio_play_urls_from_payload(payload):
            if is_allowed_media_url(candidate):
                return candidate
        raise BilibiliApiError("B 站接口没有返回可用的音频直链")

    async def fetch_live_status(self, room_id: int) -> tuple[int, str]:
        """Return (live_status, title) for one room; used by the live monitor."""
        data = await self._get_json_url(
            LIVE_API_BASE + "/room/v1/Room/get_info",
            params={"room_id": room_id},
        )
        code = data.get("code")
        if code != 0:
            message = str(data.get("message") or data.get("msg") or "未知错误")
            raise BilibiliApiError(f"B 站接口错误 {code}：{message}")
        payload = data.get("data") if isinstance(data.get("data"), dict) else {}
        live_status = self._as_int(payload.get("live_status"))
        title = str(payload.get("title") or "").strip()
        return live_status, title

    async def _get_pgc_json(
        self,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        data = await self._get_json_url(
            API_BASE + path, params=params, include_bilibili_cookie=True
        )
        code = data.get("code")
        if code != 0:
            message = str(data.get("message") or "未知错误")
            raise BilibiliApiError(f"B 站接口错误 {code}：{message}")
        payload = data.get("result")
        if not isinstance(payload, dict):
            raise BilibiliApiError("B 站接口缺少 result 字段")
        return payload

    async def _get_page_text(self, url: str) -> str:
        """Fetch a Bilibili page body as text (for server-rendered data)."""
        session = await self._get_session()
        try:
            async with session.get(url) as response:
                if response.status >= 400:
                    raise BilibiliApiError(
                        f"页面请求失败（HTTP {response.status}）"
                    )
                return await response.text(encoding="utf-8", errors="ignore")
        except asyncio.TimeoutError as exc:
            raise BilibiliApiError("请求 B 站页面超时") from exc
        except aiohttp.ClientError as exc:
            raise BilibiliApiError(f"请求 B 站页面失败：{exc}") from exc

    async def fetch_public_subtitle(
        self,
        video: VideoInfo,
        *,
        max_chars: int = 12000,
        page_limit: int = 3,
    ) -> str:
        if not video.aid or not video.cid or max_chars <= 0:
            return ""

        pages: list[tuple[int, int, str]] = []
        seen_cids: set[int] = set()
        for page in video.pages:
            if page.cid and page.cid not in seen_cids:
                pages.append((page.index, page.cid, page.title))
                seen_cids.add(page.cid)
        if not pages:
            pages.append((1, video.cid, ""))
        if page_limit > 0:
            pages = pages[:page_limit]

        results = await asyncio.gather(
            *(
                self._fetch_public_subtitle_for_cid(video.aid, cid)
                for _, cid, _ in pages
            ),
            return_exceptions=True,
        )
        sections: list[str] = []
        for (index, _, title), result in zip(pages, results):
            if isinstance(result, Exception) or not result:
                continue
            heading = f"[P{index}{' ' + title if title else ''}]"
            sections.append(f"{heading}\n{result}")
        return self._fit_subtitle_text("\n\n".join(sections), max_chars)

    async def _fetch_public_subtitle_for_cid(self, aid: int, cid: int) -> str:
        try:
            player = await self._get_api_json(
                "/x/player/v2", {"aid": aid, "cid": cid}
            )
        except BilibiliApiError:
            return ""

        subtitle = player.get("subtitle") if isinstance(player, dict) else None
        entries = subtitle.get("subtitles") if isinstance(subtitle, dict) else None
        if not isinstance(entries, list) or not entries:
            return ""

        entries = sorted(
            (entry for entry in entries if isinstance(entry, dict)),
            key=lambda entry: 0
            if str(entry.get("lan", "")).lower().startswith("zh")
            else 1,
        )
        for entry in entries:
            subtitle_url = str(entry.get("subtitle_url") or "").strip()
            if not subtitle_url:
                continue
            if subtitle_url.startswith("//"):
                subtitle_url = "https:" + subtitle_url
            if not self._host_has_suffix(subtitle_url, _SUBTITLE_HOST_SUFFIXES):
                continue
            try:
                data = await self._get_json_url(subtitle_url)
            except BilibiliApiError:
                continue
            body = data.get("body") if isinstance(data, dict) else None
            if not isinstance(body, list):
                continue
            lines = [
                str(item.get("content") or "").strip()
                for item in body
                if isinstance(item, dict) and item.get("content")
            ]
            text = "\n".join(line for line in lines if line)
            if text:
                return text
        return ""

    @staticmethod
    def _fit_subtitle_text(text: str, max_chars: int) -> str:
        """Keep representative parts of a long transcript within the LLM budget."""
        if len(text) <= max_chars:
            return text
        if max_chars <= 80:
            return text[:max_chars]

        marker = "\n\n（中间字幕已省略）\n\n"
        available = max_chars - len(marker) * 2
        chunk_size = max(1, available // 3)
        middle_start = max((len(text) - chunk_size) // 2, chunk_size)
        end_start = max(len(text) - chunk_size, middle_start + chunk_size)
        return (
            text[:chunk_size]
            + marker
            + text[middle_start : middle_start + chunk_size]
            + marker
            + text[end_start:]
        )[:max_chars]

    async def fetch_featured_comments(
        self,
        video: VideoInfo,
        *,
        candidate_limit: int = 8,
        comment_limit: int = 2,
        reply_limit: int = 2,
    ) -> list[FeaturedComment]:
        """Randomly pick leading Bilibili hot comments with their replies."""
        if not video.aid or candidate_limit <= 0 or comment_limit <= 0:
            return []
        payload = await self._get_api_json(
            "/x/v2/reply",
            {
                "oid": video.aid,
                "type": 1,
                "pn": 1,
                "sort": 2,
            },
        )
        replies = payload.get("replies") if isinstance(payload, dict) else None
        if not isinstance(replies, list):
            return []

        candidates: list[FeaturedComment] = []
        for reply in replies:
            comment = self._comment_from_payload(reply, reply_limit=reply_limit)
            if comment:
                candidates.append(comment)
        if not candidates:
            return []
        pool_size = min(candidate_limit, len(candidates))
        pick_count = min(comment_limit, pool_size)
        picked_indices = sorted(random.sample(range(pool_size), k=pick_count))
        return [candidates[index] for index in picked_indices]

    async def fetch_image_data_uri(
        self,
        url: str,
        *,
        max_bytes: int = 8_000_000,
        max_dimension: int = 1280,
    ) -> str:
        """Download, decode and normalize an image before HTML rendering."""
        if not url:
            return ""
        session = await self._get_session()
        failures: list[str] = []
        request_timeout = aiohttp.ClientTimeout(
            total=min(self.timeout_seconds, 8),
            connect=min(self.timeout_seconds, 5),
            sock_read=min(self.timeout_seconds, 8),
        )
        for candidate_url in self._image_url_candidates(url):
            try:
                async with session.get(
                    candidate_url,
                    headers={
                        "Accept": (
                            # Do not advertise AVIF here: Pillow builds used by
                            # AstrBot commonly cannot decode it. The CDN then
                            # returns a JPEG/PNG/WebP that we can verify first.
                            "image/jpeg,image/png,image/webp,image/apng,"
                            "image/*;q=0.8,*/*;q=0.5"
                        )
                    },
                    timeout=request_timeout,
                ) as response:
                    if response.status >= 400:
                        failures.append(f"HTTP {response.status}")
                        continue
                    content_length = int(response.headers.get("Content-Length") or 0)
                    if content_length > max_bytes:
                        failures.append("图片文件过大")
                        continue
                    # StreamReader.read(n) may return only the currently buffered
                    # chunk. Accumulate until EOF, otherwise valid JPEGs are often
                    # handed to Pillow as truncated files.
                    body = bytearray()
                    while len(body) <= max_bytes:
                        chunk = await response.content.read(
                            min(64 * 1024, max_bytes + 1 - len(body))
                        )
                        if not chunk:
                            break
                        body.extend(chunk)
                    content = bytes(body)
                    if len(content) > max_bytes:
                        failures.append("图片文件过大")
                        continue
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                failures.append(type(exc).__name__)
                continue

            try:
                with Image.open(BytesIO(content)) as source:
                    source.load()
                    image = ImageOps.exif_transpose(source)
                    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                    if image.mode in {"RGBA", "LA"}:
                        background = Image.new("RGB", image.size, "white")
                        background.paste(image, mask=image.getchannel("A"))
                        image = background
                    elif image.mode != "RGB":
                        image = image.convert("RGB")
                    normalized = BytesIO()
                    image.save(normalized, format="JPEG", quality=90)
            except Exception as exc:
                failures.append(f"解码失败：{type(exc).__name__}")
                continue
            encoded = base64.b64encode(normalized.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{encoded}"

        logger.warning(
            "B站图片下载失败，已尝试备用图床：%s（%s）",
            url,
            "、".join(failures[-4:]) or "无可用图片地址",
        )
        return ""

    async def fetch_yaohud_direct_url(self, video_url: str, api_key: str) -> str:
        """Optionally resolve one temporary media URL through Yaohud doc/57."""
        api_key = api_key.strip()
        if not api_key:
            return ""
        response = await self._get_json_url(
            YAO_HUD_ENDPOINT,
            params={"key": api_key, "url": video_url},
        )
        # The service has used both code-based and status-based response formats.
        # A usable trusted media URL is the strongest success signal.
        direct_url = find_direct_media_url(response)
        if direct_url:
            return direct_url

        code = response.get("code")
        message = str(
            response.get("msg")
            or response.get("message")
            or response.get("error")
            or response.get("detail")
            or ""
        ).strip()
        if code not in (None, 0, 200, "0", "200"):
            raise BilibiliApiError(
                f"妖狐接口错误 {code}：{message or '请检查 API Key 是否开通 B 站直链服务'}"
            )
        if code is None and message:
            raise BilibiliApiError(f"妖狐接口未返回视频直链：{message}")
        fields = "、".join(sorted(str(key) for key in response)[:8]) or "无"
        raise BilibiliApiError(
            f"妖狐接口未返回视频直链（响应字段：{fields}）"
        )

    async def download_media(
        self,
        url: str,
        destination: Path,
        *,
        max_bytes: int,
        timeout_seconds: int,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        """Stream one trusted temporary media URL to a local file.

        Returns the response Content-Type so callers can pick a file
        extension. Video and audio downloads share this implementation.
        """
        if max_bytes <= 0 or not is_allowed_media_url(url):
            raise BilibiliApiError("媒体直链无效或不受信任")

        timeout = aiohttp.ClientTimeout(
            total=max(float(timeout_seconds), 10.0),
            connect=min(max(float(timeout_seconds), 10.0), 15.0),
            sock_read=max(float(timeout_seconds), 10.0),
        )
        session = await self._get_session()
        current_url = url
        for _ in range(4):
            if cancel_event and cancel_event.is_set():
                raise BilibiliApiError("媒体下载已取消")
            try:
                response = await session.get(
                    current_url,
                    allow_redirects=False,
                    timeout=timeout,
                    headers={
                        "Accept": "video/mp4,audio/mp4,audio/mpeg,*/*;q=0.5"
                    },
                )
            except asyncio.TimeoutError as exc:
                raise BilibiliApiError("媒体下载超时") from exc
            except aiohttp.ClientError as exc:
                raise BilibiliApiError(f"媒体下载请求失败：{exc}") from exc

            async with response:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        raise BilibiliApiError("媒体下载跳转地址缺失")
                    current_url = urljoin(current_url, location)
                    if not is_allowed_media_url(current_url):
                        raise BilibiliApiError("媒体下载跳转到了不受信任的地址")
                    continue
                if response.status >= 400:
                    raise BilibiliApiError(f"媒体下载失败（HTTP {response.status}）")
                declared_size = int(response.headers.get("Content-Length") or 0)
                if declared_size > max_bytes:
                    raise BilibiliApiError("媒体文件超过后台设定的大小上限")
                content_type = response.headers.get("Content-Type", "").lower()
                if content_type and not (
                    content_type.startswith("video/")
                    or content_type.startswith("audio/")
                    or content_type.startswith("application/octet-stream")
                ):
                    raise BilibiliApiError("媒体直链没有返回媒体文件")

                received = 0
                with destination.open("wb") as output:
                    while True:
                        if cancel_event and cancel_event.is_set():
                            raise BilibiliApiError("媒体下载已取消")
                        chunk = await response.content.read(256 * 1024)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > max_bytes:
                            raise BilibiliApiError("媒体文件超过后台设定的大小上限")
                        output.write(chunk)
                if received <= 0:
                    raise BilibiliApiError("媒体文件为空")
                return content_type or ""
        raise BilibiliApiError("媒体下载跳转次数过多")

    async def download_direct_video(
        self,
        url: str,
        destination: Path,
        *,
        max_bytes: int,
        timeout_seconds: int,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        """Backward-compatible wrapper around download_media for video URLs."""
        await self.download_media(
            url,
            destination,
            max_bytes=max_bytes,
            timeout_seconds=timeout_seconds,
            cancel_event=cancel_event,
        )

    async def _get_api_json(
        self,
        path: str,
        params: dict[str, Any],
        *,
        base: str = API_BASE,
    ) -> dict[str, Any]:
        data = await self._get_json_url(
            base + path, params=params, include_bilibili_cookie=True
        )
        if not isinstance(data, dict):
            raise BilibiliApiError("B 站接口返回了无效数据")
        code = data.get("code")
        if code != 0:
            message = str(data.get("message") or data.get("msg") or "未知错误")
            raise BilibiliApiError(f"B 站接口错误 {code}：{message}")
        payload = data.get("data")
        if not isinstance(payload, dict):
            raise BilibiliApiError("B 站接口缺少 data 字段")
        return payload

    async def _get_json_url(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        include_bilibili_cookie: bool = False,
    ) -> dict[str, Any]:
        session = await self._get_session()
        headers: dict[str, str] | None = None
        if include_bilibili_cookie and self._sessdata:
            headers = {"Cookie": f"SESSDATA={self._sessdata}"}
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status >= 400:
                    raise BilibiliApiError(f"HTTP 请求失败（{response.status}）")
                raw = await response.text(encoding="utf-8", errors="ignore")
        except asyncio.TimeoutError as exc:
            raise BilibiliApiError("请求 B 站接口超时") from exc
        except aiohttp.ClientError as exc:
            raise BilibiliApiError(f"请求 B 站接口失败：{exc}") from exc
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BilibiliApiError("B 站接口没有返回 JSON") from exc
        if not isinstance(decoded, dict):
            raise BilibiliApiError("B 站接口返回的 JSON 格式无效")
        return decoded

    @staticmethod
    def _validate_bilibili_url(url: str) -> None:
        try:
            parsed = urlparse(url)
            port = parsed.port
        except ValueError as exc:
            raise BilibiliApiError("B 站链接端口无效") from exc
        host = (parsed.hostname or "").lower()
        allowed = host in _SHORT_HOSTS or host in _PAGE_HOSTS or host.endswith(".bilibili.com")
        if (
            parsed.scheme != "https"
            or port not in (None, 443)
            or parsed.username
            or parsed.password
            or not allowed
        ):
            raise BilibiliApiError("拒绝访问非 B 站链接")

    @staticmethod
    def _normalize_sessdata(value: str) -> str:
        """Accept a SESSDATA value without ever forwarding it to non-Bili hosts."""
        sessdata = str(value or "").strip()
        if sessdata.startswith("SESSDATA="):
            sessdata = sessdata[len("SESSDATA=") :].split(";", 1)[0].strip()
        if "\r" in sessdata or "\n" in sessdata:
            return ""
        return sessdata

    @staticmethod
    def _host_has_suffix(url: str, suffixes: tuple[str, ...]) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and any(
            host == suffix[1:] or host.endswith(suffix) for suffix in suffixes
        )

    @staticmethod
    def _image_url_candidates(url: str) -> list[str]:
        """Return fast Bilibili image-CDN alternatives for one trusted image URL."""
        if url.startswith("//"):
            url = "https:" + url
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not any(
            host == suffix[1:] or host.endswith(suffix)
            for suffix in _IMAGE_HOST_SUFFIXES
        ):
            return []

        candidates: list[str] = []
        if host.endswith(".hdslb.com"):
            for cdn_host in ("i0.hdslb.com", "i1.hdslb.com", "i2.hdslb.com", "i3.hdslb.com"):
                candidates.append(
                    urlunsplit(("https", cdn_host, parsed.path, parsed.query, ""))
                )
        candidates.append(urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, "")))
        return list(dict.fromkeys(candidates))

    @staticmethod
    def _as_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _comment_from_payload(
        cls,
        payload: Any,
        *,
        reply_limit: int,
    ) -> FeaturedComment | None:
        if not isinstance(payload, dict):
            return None
        content = payload.get("content")
        member = payload.get("member")
        message = (
            str(content.get("message") or "").strip()
            if isinstance(content, dict)
            else ""
        )
        if not message:
            return None
        author_name = (
            str(member.get("uname") or "").strip()
            if isinstance(member, dict)
            else ""
        )
        author_face_url = (
            str(member.get("avatar") or "").strip()
            if isinstance(member, dict)
            else ""
        )
        replies = payload.get("replies")
        parsed_replies: list[CommentReply] = []
        if isinstance(replies, list) and reply_limit > 0:
            seen_reply_ids: set[str] = set()
            for reply in replies:
                if isinstance(reply, dict):
                    reply_id = str(reply.get("rpid") or "")
                    if reply_id and reply_id in seen_reply_ids:
                        continue
                    if reply_id:
                        seen_reply_ids.add(reply_id)
                parsed = cls._reply_from_payload(reply)
                if parsed:
                    parsed_replies.append(parsed)
                if len(parsed_replies) >= reply_limit:
                    break
        return FeaturedComment(
            author_name=author_name or "B站用户",
            author_face_url=author_face_url,
            content=message,
            like_count=cls._as_int(payload.get("like")),
            replies=parsed_replies,
        )

    @classmethod
    def _reply_from_payload(cls, payload: Any) -> CommentReply | None:
        if not isinstance(payload, dict):
            return None
        content = payload.get("content")
        member = payload.get("member")
        message = (
            str(content.get("message") or "").strip()
            if isinstance(content, dict)
            else ""
        )
        if not message:
            return None
        author_name = (
            str(member.get("uname") or "").strip()
            if isinstance(member, dict)
            else ""
        )
        author_face_url = (
            str(member.get("avatar") or "").strip()
            if isinstance(member, dict)
            else ""
        )
        return CommentReply(
            author_name=author_name or "B站用户",
            author_face_url=author_face_url,
            content=message,
            like_count=cls._as_int(payload.get("like")),
        )
