from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import secrets
import time
from typing import Callable


@dataclass(frozen=True)
class MediaItem:
    data: bytes
    mime_type: str
    filename: str
    expires_at: float


class MediaStore:
    """Bounded in-memory store for short-lived, capability-URL media."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> None:
        self._clock = clock
        self._token_factory = token_factory
        self._items: OrderedDict[str, MediaItem] = OrderedDict()
        self._total_bytes = 0

    def put(
        self,
        data: bytes,
        mime_type: str,
        filename: str,
        *,
        ttl_seconds: int,
        max_items: int,
        max_total_bytes: int,
    ) -> tuple[str, MediaItem]:
        if len(data) > max_total_bytes:
            raise ValueError("generated image exceeds media cache size limit")
        self._purge_expired()
        while self._items and (
            len(self._items) >= max_items or self._total_bytes + len(data) > max_total_bytes
        ):
            _, removed = self._items.popitem(last=False)
            self._total_bytes -= len(removed.data)
        token = self._token_factory()
        while token in self._items:
            token = self._token_factory()
        item = MediaItem(
            data=data,
            mime_type=mime_type,
            filename=filename,
            expires_at=self._clock() + ttl_seconds,
        )
        self._items[token] = item
        self._total_bytes += len(data)
        return token, item

    def get(self, token: str) -> MediaItem | None:
        self._purge_expired()
        return self._items.get(token)

    def remaining_seconds(self, item: MediaItem) -> int:
        return max(0, int(item.expires_at - self._clock()))

    def clear(self) -> None:
        self._items.clear()
        self._total_bytes = 0

    def _purge_expired(self) -> None:
        now = self._clock()
        expired = [token for token, item in self._items.items() if item.expires_at <= now]
        for token in expired:
            removed = self._items.pop(token)
            self._total_bytes -= len(removed.data)
