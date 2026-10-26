"""Bounded, expiring in-process storage for generated results and garment cutouts.

Results and cutouts share one byte budget because they compete for the same
process memory.  Entries expire a fixed time after they are stored; when the
store is full the least recently read or written entry is evicted first.

The store lives in a single process: it is not shared between workers and is
cleared on restart.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from app.schemas.generation import ImageAsset


class ImageTooLargeToStoreError(Exception):
    """Raised when one image is larger than the whole store budget."""


@dataclass(frozen=True)
class _Entry:
    kind: str
    image: ImageAsset
    size: int
    expires_at: float


@dataclass(frozen=True)
class StoreResult:
    image_id: str
    evicted: int
    expired: int


@dataclass(frozen=True)
class ImageStoreStats:
    items: int
    bytes: int
    max_items: int
    max_bytes: int
    ttl_seconds: float
    stored_total: int
    evicted_total: int
    expired_total: int
    rejected_total: int


class TemporaryImageStore:
    def __init__(self, ttl_seconds: float, max_items: int, max_bytes: int, clock: Callable[[], float] = time.monotonic):
        if ttl_seconds <= 0 or max_items <= 0 or max_bytes <= 0:
            raise ValueError("image store limits must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self.max_bytes = max_bytes
        self._clock = clock
        self._lock = threading.Lock()
        # Ordered from least to most recently used.
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._bytes = 0
        self._stored_total = 0
        self._evicted_total = 0
        self._expired_total = 0
        self._rejected_total = 0

    def put(self, kind: str, image: ImageAsset) -> StoreResult:
        size = len(image.content)
        with self._lock:
            if size > self.max_bytes:
                self._rejected_total += 1
                raise ImageTooLargeToStoreError(f"{size} bytes exceeds the {self.max_bytes} byte store budget")
            now = self._clock()
            expired = self._remove_expired(now)
            evicted = 0
            while self._entries and (len(self._entries) >= self.max_items or self._bytes + size > self.max_bytes):
                self._remove(next(iter(self._entries)))
                evicted += 1
            image_id = str(uuid4())
            self._entries[image_id] = _Entry(kind, image, size, now + self.ttl_seconds)
            self._bytes += size
            self._stored_total += 1
            self._evicted_total += evicted
            return StoreResult(image_id, evicted, expired)

    def get(self, kind: str, image_id: str) -> ImageAsset | None:
        with self._lock:
            entry = self._entries.get(image_id)
            if entry is None or entry.kind != kind:
                return None
            if entry.expires_at <= self._clock():
                self._remove(image_id)
                self._expired_total += 1
                return None
            self._entries.move_to_end(image_id)
            return entry.image

    def stats(self) -> ImageStoreStats:
        with self._lock:
            return ImageStoreStats(
                items=len(self._entries), bytes=self._bytes, max_items=self.max_items, max_bytes=self.max_bytes,
                ttl_seconds=self.ttl_seconds, stored_total=self._stored_total, evicted_total=self._evicted_total,
                expired_total=self._expired_total, rejected_total=self._rejected_total,
            )

    def _remove(self, image_id: str) -> None:
        entry = self._entries.pop(image_id)
        self._bytes -= entry.size

    def _remove_expired(self, now: float) -> int:
        # Reads reorder entries, so expiry order differs from LRU order; the store is small enough to scan.
        expired_ids = [image_id for image_id, entry in self._entries.items() if entry.expires_at <= now]
        for image_id in expired_ids:
            self._remove(image_id)
        self._expired_total += len(expired_ids)
        return len(expired_ids)
