"""Pure subscription storage and state transitions for the live monitor.

Kept free of AstrBot imports so it can be unit-tested directly.
"""

from __future__ import annotations

import json

# 上限防滥用：单个会话最多订阅数 / 全插件最多订阅对数 / 同一直播间最多推送会话数。
MAX_PER_UMO = 10
MAX_TOTAL = 50
MAX_UMOS_PER_ROOM = 20


class LiveSubscriptionStore:
    """Track which conversations want notifications for which live rooms."""

    def __init__(self) -> None:
        # key: (room_id, unified_msg_origin)
        self._subs: dict[tuple[int, str], None] = {}

    @classmethod
    def from_json(cls, raw: str | None) -> "LiveSubscriptionStore":
        store = cls()
        for item in _parse_entries(raw):
            store._subs[(item[0], item[1])] = None
        return store

    def to_json(self) -> str:
        return json.dumps(
            [f"{room}@{umo}" for room, umo in sorted(self._subs)],
            ensure_ascii=False,
        )

    def add(self, room_id: int, umo: str) -> tuple[bool, str]:
        """Register one subscription. Returns (changed, message)."""
        if (room_id, umo) in self._subs:
            return False, "本会话已订阅该直播间。"
        if self.count_for_umo(umo) >= MAX_PER_UMO:
            return False, f"本会话最多订阅 {MAX_PER_UMO} 个直播间，请先取消一部分。"
        if len(self._subs) >= MAX_TOTAL:
            return False, "订阅总数已达上限，请联系管理员清理。"
        if len(self.umos_for(room_id)) >= MAX_UMOS_PER_ROOM:
            return False, "该直播间订阅的会话数已达上限。"
        self._subs[(room_id, umo)] = None
        return True, "ok"

    def remove(self, room_id: int, umo: str) -> tuple[bool, str]:
        if (room_id, umo) not in self._subs:
            return False, "本会话没有订阅该直播间。"
        del self._subs[(room_id, umo)]
        return True, "ok"

    def remove_umo(self, umo: str) -> int:
        """Drop every subscription of one conversation; returns removed count."""
        targets = [room for room, target in self._subs if target == umo]
        for room in targets:
            del self._subs[(room, umo)]
        return len(targets)

    def umos_for(self, room_id: int) -> list[str]:
        return sorted(
            umo for room, umo in self._subs if room == room_id
        )

    def count_for_umo(self, umo: str) -> int:
        return sum(1 for _, target in self._subs if target == umo)

    def rooms(self) -> list[int]:
        return sorted({room for room, _ in self._subs})

    def items(self) -> list[tuple[int, str]]:
        return sorted(self._subs)

    def __len__(self) -> int:
        return len(self._subs)


def _parse_entries(raw: str | None) -> list[tuple[int, str]]:
    if not raw:
        return []
    try:
        entries = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(entries, list):
        return []
    parsed: list[tuple[int, str]] = []
    for entry in entries:
        if not isinstance(entry, str) or "@" not in entry:
            continue
        room_text, _, umo = entry.partition("@")
        if room_text.isdigit() and umo.strip():
            parsed.append((int(room_text), umo.strip()))
    return parsed


def should_notify_live_start(previous: int | None, current: int) -> bool:
    """Notify only on an observed transition into live (status 1).

    previous None means the room was never polled in this session: no
    notification then, so a plugin restart never spams every live room.
    previous 2 (轮播中) also counts as not-live.
    """
    if current != 1:
        return False
    return previous in (0, 2)


def should_notify_live_end(previous: int | None, current: int) -> bool:
    """True when the room transitioned out of a live state."""
    if previous != 1:
        return False
    return current in (0, 2)
