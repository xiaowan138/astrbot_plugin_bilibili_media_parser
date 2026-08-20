from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any, Iterator, Literal
from urllib.parse import unquote


ReferenceKind = Literal["bvid", "aid", "auid", "url"]

_BVID_RE = re.compile(r"(?<![0-9A-Za-z])BV[0-9A-Za-z]{10}(?![0-9A-Za-z])", re.I)
_AID_RE = re.compile(r"(?<![0-9A-Za-z])av(\d{1,20})(?!\d)", re.I)
_AUID_RE = re.compile(r"(?<![0-9A-Za-z])au(\d{1,20})(?!\d)", re.I)
_BILI_URI_RE = re.compile(r"bilibili://video/(BV[0-9A-Za-z]{10}|\d{1,20})", re.I)
_URL_RE = re.compile(
    r"(?:(?:https?):?//)?(?:"
    r"(?:www\.|m\.|space\.)?bilibili\.com/[^\s<>\"']+"
    r"|b23\.tv/[^\s<>\"']+"
    r"|(?:www\.)?bili2233\.cn/[^\s<>\"']+"
    r")",
    re.I,
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


def _reference_from_text(value: str, source: str) -> VideoReference | None:
    text = _decode_text(value)

    uri_match = _BILI_URI_RE.search(text)
    if uri_match:
        uri_value = uri_match.group(1)
        if uri_value.lower().startswith("bv"):
            return VideoReference("bvid", "BV" + uri_value[2:], source)
        return VideoReference("aid", uri_value, source)

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

    # Detect audio URLs before falling through to the generic URL handler.
    audio_au_match = re.search(
        r"(?:www\.|m\.)?bilibili\.com/audio/au(\d{1,20})",
        url,
        re.I,
    )
    if audio_au_match:
        return VideoReference("auid", audio_au_match.group(1), source)

    return VideoReference("url", url, source)


def extract_video_reference(*payloads: Any) -> VideoReference | None:
    """Find a video reference in text, message components, or raw adapter JSON."""
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

