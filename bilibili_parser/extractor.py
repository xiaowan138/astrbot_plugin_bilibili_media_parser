from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any, Iterator, Literal
from urllib.parse import unquote, urlparse


ReferenceKind = Literal[
    "bvid", "aid", "auid", "article", "live", "dynamic", "ep", "ss", "url"
]

_BVID_RE = re.compile(r"(?<![0-9A-Za-z])BV[0-9A-Za-z]{10}(?![0-9A-Za-z])", re.I)
_AID_RE = re.compile(r"(?<![0-9A-Za-z])av(\d{1,20})(?!\d)", re.I)
_AUID_RE = re.compile(r"(?<![0-9A-Za-z])au(\d{1,20})(?!\d)", re.I)
_BILI_URI_RE = re.compile(
    r"bilibili://(video|live|opus|article|audio)/"
    r"(BV[0-9A-Za-z]{10}|cv\d{1,20}|au\d{1,20}|\d{1,20})",
    re.I,
)
_URL_RE = re.compile(
    r"(?:(?:https?):?//)?(?:"
    r"(?:www\.|m\.|space\.)?bilibili\.com/[^\s<>\"']+"
    r"|live\.bilibili\.com/[^\s<>\"']+"
    r"|t\.bilibili\.com/[^\s<>\"']+"
    r"|b23\.tv/[^\s<>\"']+"
    r"|(?:www\.)?bili2233\.cn/[^\s<>\"']+"
    r")",
    re.I,
)
# 只按全角标点/括号切词：这些字符永远不会出现在 B 站 URL 里，切词可以
# 让多个链接各自独立识别，同时不破坏半角字符组成的 URL。
_TOKEN_SPLIT_RE = re.compile(
    r"[\s【】「」『』《》〈〉（）　“”‘’…—·，。、；：！？]+"
)
_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")
_TRAILING_PUNCTUATION = "。，、；：！？,.!?:;)]}〉》」』】"


@dataclass(frozen=True, slots=True)
class VideoReference:
    kind: ReferenceKind
    value: str
    source: str = "message"

    @property
    def hint_key(self) -> str:
        if self.kind == "aid":
            return f"av{self.value}"
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


def _decode_text(value: str) -> str:
    decoded = value
    for _ in range(3):
        previous = decoded
        decoded = html.unescape(decoded).replace("\\/", "/")
        decoded = _UNICODE_ESCAPE_RE.sub(
            lambda match: chr(int(match.group(1), 16)), decoded
        )
        try:
            decoded = unquote(decoded)
        except (UnicodeDecodeError, ValueError):
            pass
        if decoded == previous:
            break
    return decoded


def _iter_strings(value: Any, *, depth: int = 0, seen: set[int] | None = None) -> Iterator[str]:
    if value is None or depth > 7:
        return
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, (bytes, bytearray)):
        yield bytes(value).decode("utf-8", errors="ignore")
        return
    if isinstance(value, (int, float, bool)):
        return

    if seen is None:
        seen = set()
    object_id = id(value)
    if object_id in seen:
        return
    seen.add(object_id)

    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from _iter_strings(item, depth=depth + 1, seen=seen)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _iter_strings(item, depth=depth + 1, seen=seen)
        return

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            yield from _iter_strings(model_dump(), depth=depth + 1, seen=seen)
            return
        except Exception:
            pass

    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        yield from _iter_strings(attributes, depth=depth + 1, seen=seen)


def _reference_from_uri(scheme: str, value: str, source: str) -> VideoReference:
    scheme = scheme.lower()
    if scheme == "live":
        return VideoReference("live", value, source)
    if scheme == "opus":
        return VideoReference("dynamic", value, source)
    if scheme == "audio":
        if value.lower().startswith("au"):
            return VideoReference("auid", value[2:], source)
        return VideoReference("auid", value, source)
    if value.lower().startswith("cv"):
        return VideoReference("article", value[2:], source)
    if value.lower().startswith("bv"):
        return VideoReference("bvid", "BV" + value[2:], source)
    return VideoReference("aid", value, source)


def _reference_from_text(value: str, source: str) -> VideoReference | None:
    text = _decode_text(value)

    uri_match = _BILI_URI_RE.search(text)
    if uri_match:
        return _reference_from_uri(uri_match.group(1), uri_match.group(2), source)

    bvid_match = _BVID_RE.search(text)
    if bvid_match:
        bvid = bvid_match.group(0)
        return VideoReference("bvid", "BV" + bvid[2:], source)

    aid_match = _AID_RE.search(text)
    if aid_match:
        return VideoReference("aid", aid_match.group(1), source)

    auid_match = _AUID_RE.search(text)
    if auid_match:
        return VideoReference("auid", auid_match.group(1), source)

    url_match = _URL_RE.search(text)
    if not url_match:
        return None
    url = url_match.group(0).rstrip(_TRAILING_PUNCTUATION)
    if url.startswith("//"):
        url = "https:" + url
    elif not re.match(r"https?://", url, re.I):
        url = "https://" + url
    elif url.lower().startswith("http://"):
        url = "https://" + url[7:]

    # Detect content-type URLs before falling through to the generic handler.
    # Order matters: audio/read/opus paths are on www.bilibili.com, live/t are
    # separate hosts; each pattern is specific enough to avoid ambiguity.
    audio_au_match = re.search(
        r"(?:www\.|m\.)?bilibili\.com/audio/au(\d{1,20})",
        url,
        re.I,
    )
    if audio_au_match:
        return VideoReference("auid", audio_au_match.group(1), source)

    article_match = re.search(
        r"(?:www\.|m\.)?bilibili\.com/read/cv(\d{1,20})",
        url,
        re.I,
    )
    if article_match:
        return VideoReference("article", article_match.group(1), source)

    opus_match = re.search(
        r"(?:www\.|m\.)?bilibili\.com/opus/(\d{1,20})",
        url,
        re.I,
    )
    if opus_match:
        return VideoReference("dynamic", opus_match.group(1), source)

    t_bili_match = re.search(r"t\.bilibili\.com/(\d{1,20})", url, re.I)
    if t_bili_match:
        return VideoReference("dynamic", t_bili_match.group(1), source)

    live_match = re.search(
        r"live\.bilibili\.com/(?:h5/|blanc/|popup/)?(\d{1,20})", url, re.I
    )
    if live_match:
        return VideoReference("live", live_match.group(1), source)

    bangumi_ep_match = re.search(
        r"bilibili\.com/bangumi/play/ep(\d{1,20})", url, re.I
    )
    if bangumi_ep_match:
        return VideoReference("ep", bangumi_ep_match.group(1), source)

    bangumi_ss_match = re.search(
        r"bilibili\.com/bangumi/play/ss(\d{1,20})", url, re.I
    )
    if bangumi_ss_match:
        return VideoReference("ss", bangumi_ss_match.group(1), source)

    # UP 主空间页指向的不是具体内容：继续解析只会抓到主页推荐位里的
    # 随机视频。带上 BV 的 space 链接在更早的正则分支已经命中，不会走到这里。
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return None
    if host == "space.bilibili.com":
        return None

    return VideoReference("url", url, source)


def extract_video_reference(*payloads: Any) -> VideoReference | None:
    """Find the first video reference in text, components, or raw adapter JSON."""
    for index, payload in enumerate(payloads):
        source = "message" if index == 0 else "raw_message"
        for value in _iter_strings(payload):
            reference = _reference_from_text(value, source)
            if reference:
                return reference

            # Some OneBot JSON components keep the mini-app payload as JSON text.
            stripped = value.strip()
            if stripped.startswith(("{", "[")):
                try:
                    decoded = json.loads(stripped)
                except (json.JSONDecodeError, TypeError):
                    continue
                for nested in _iter_strings(decoded):
                    reference = _reference_from_text(nested, "mini_program")
                    if reference:
                        return reference
    return None


def _collect_references_from_string(
    value: str,
    source: str,
    references: list[VideoReference],
    seen: set[tuple[str, str]],
) -> None:
    stripped = value.strip()
    if stripped.startswith(("{", "[")):
        try:
            decoded = json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            decoded = None
        if decoded is not None:
            for nested in _iter_strings(decoded):
                _collect_references_from_string(
                    nested, "mini_program", references, seen
                )
            return

    for token in _TOKEN_SPLIT_RE.split(_decode_text(value)):
        reference = _reference_from_text(token, source)
        if reference is None:
            continue
        key = (reference.kind, reference.value)
        if key in seen:
            continue
        seen.add(key)
        references.append(reference)


def extract_video_references(*payloads: Any) -> list[VideoReference]:
    """Find every distinct Bilibili reference, in order of first appearance."""
    references: list[VideoReference] = []
    seen: set[tuple[str, str]] = set()
    for payload in payloads:
        for value in _iter_strings(payload):
            _collect_references_from_string(value, "message", references, seen)
    return references

