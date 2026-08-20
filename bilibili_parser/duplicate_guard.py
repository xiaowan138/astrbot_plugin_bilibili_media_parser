from __future__ import annotations

import asyncio
import time
from collections.abc import Callable


class DuplicateGuard:
    """Atomically reject keys seen within a monotonic time window."""

    def __init__(
        self,
        window_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window_seconds = max(float(window_seconds), 0.0)
        self._clock = clock
        self._seen: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def check_and_mark(self, scope: str, video_id: str) -> bool:
        """Return True when the key is a duplicate; otherwise record it."""
        if self.window_seconds <= 0:
            return False

        now = self._clock()
        key = f"{scope}\x1f{video_id}"
        async with self._lock:
            previous = self._seen.get(key)
            if previous is not None and now - previous < self.window_seconds:
                return True

            self._seen[key] = now
            if len(self._seen) > 2048:
                cutoff = now - self.window_seconds
                self._seen = {
                    item_key: timestamp
                    for item_key, timestamp in self._seen.items()
                    if timestamp >= cutoff
                }
                while len(self._seen) > 2048:
                    oldest_key = min(self._seen, key=self._seen.get)
                    self._seen.pop(oldest_key, None)
            return False

    async def clear(self) -> None:
        async with self._lock:
            self._seen.clear()

    async def forget(self, scope: str, video_id: str) -> None:
        """Release a reservation after the first parse attempt failed."""
        key = f"{scope}\x1f{video_id}"
        async with self._lock:
            self._seen.pop(key, None)
