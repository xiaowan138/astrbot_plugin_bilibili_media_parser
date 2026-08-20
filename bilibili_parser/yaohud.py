from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


YAO_HUD_ENDPOINT = "https://api.yaohud.cn/api/v6/video/bili"
_DIRECT_MEDIA_SUFFIXES = (".bilivideo.com",)
_POSITIVE_KEYS = ("video", "play", "download", "durl", "base_url", "baseurl", "url")
_NEGATIVE_KEYS = ("cover", "pic", "image", "avatar", "face", "first_frame")


def is_allowed_media_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and port in (None, 443)
        and any(host == suffix[1:] or host.endswith(suffix) for suffix in _DIRECT_MEDIA_SUFFIXES)
    )


def find_direct_media_url(payload: Any) -> str:
    """Best-effort adapter for Yaohud's undocumented success payload."""
    candidates: list[tuple[int, str]] = []

    def walk(value: Any, path: tuple[str, ...], depth: int = 0) -> None:
        if depth > 10:
            return
        if isinstance(value, str):
            if not is_allowed_media_url(value):
                return
            joined = ".".join(path).lower()
            score = 20
            if any(token in joined for token in _POSITIVE_KEYS):
                score += 20
            if any(token in joined for token in _NEGATIVE_KEYS):
                score -= 100
            candidates.append((score, value))
            return
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, path + (str(key),), depth + 1)
            return
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                walk(item, path + (str(index),), depth + 1)

    walk(payload, ())
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]
