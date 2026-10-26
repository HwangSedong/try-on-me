import threading

import pytest

from app.schemas.generation import ImageAsset
from app.services.temporary_image_store import ImageTooLargeToStoreError, TemporaryImageStore


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def image(size: int) -> ImageAsset:
    return ImageAsset(b"x" * size, "image/png")


def store(ttl: float = 60, max_items: int = 10, max_bytes: int = 1000, clock: Clock | None = None) -> TemporaryImageStore:
    return TemporaryImageStore(ttl, max_items, max_bytes, clock or Clock())


def test_returns_stored_image_only_for_its_own_kind():
    images = store()
    saved = images.put("result", image(10))

    assert images.get("result", saved.image_id).content == b"x" * 10
    assert images.get("cutout", saved.image_id) is None


def test_unknown_id_returns_none():
    assert store().get("result", "missing") is None


def test_expires_entries_after_ttl():
    clock = Clock()
    images = store(ttl=30, clock=clock)
    saved = images.put("result", image(10))

    clock.now += 29.9
    assert images.get("result", saved.image_id) is not None
    clock.now += 0.1
    assert images.get("result", saved.image_id) is None

    stats = images.stats()
    assert (stats.items, stats.bytes, stats.expired_total) == (0, 0, 1)


def test_reading_does_not_extend_ttl():
    clock = Clock()
    images = store(ttl=30, clock=clock)
    saved = images.put("result", image(10))

    clock.now += 20
    images.get("result", saved.image_id)
    clock.now += 10

    assert images.get("result", saved.image_id) is None


def test_put_purges_expired_entries_before_evicting_live_ones():
    clock = Clock()
    images = store(ttl=30, max_items=2, clock=clock)
    old = images.put("result", image(10))
    clock.now += 20
    live = images.put("result", image(10))
    clock.now += 15  # only the first entry has expired

    saved = images.put("result", image(10))

    assert (saved.expired, saved.evicted) == (1, 0)
    assert images.get("result", old.image_id) is None
    assert images.get("result", live.image_id) is not None


def test_evicts_least_recently_used_entry_when_item_limit_is_reached():
    images = store(max_items=3)
    first, second, third = (images.put("result", image(10)) for _ in range(3))
    images.get("result", first.image_id)  # first becomes most recently used

    saved = images.put("result", image(10))

    assert saved.evicted == 1
    assert images.get("result", second.image_id) is None
    assert all(images.get("result", entry.image_id) is not None for entry in (first, third, saved))


def test_evicts_until_the_new_image_fits_the_byte_budget():
    images = store(max_bytes=100)
    first = images.put("result", image(40))
    second = images.put("cutout", image(40))

    saved = images.put("result", image(70))

    assert saved.evicted == 2
    assert images.get("result", first.image_id) is None
    assert images.get("cutout", second.image_id) is None
    assert images.stats().bytes == 70


def test_results_and_cutouts_share_one_budget():
    images = store(max_bytes=100)
    images.put("cutout", image(60))
    images.put("result", image(60))

    stats = images.stats()
    assert (stats.items, stats.bytes, stats.evicted_total) == (1, 60, 1)


def test_rejects_an_image_larger_than_the_budget_without_touching_existing_entries():
    images = store(max_bytes=100)
    kept = images.put("result", image(90))

    with pytest.raises(ImageTooLargeToStoreError):
        images.put("result", image(101))

    stats = images.stats()
    assert images.get("result", kept.image_id) is not None
    assert (stats.items, stats.bytes, stats.rejected_total, stats.evicted_total) == (1, 90, 1, 0)


def test_accepts_an_image_exactly_the_size_of_the_budget():
    images = store(max_bytes=100)
    images.put("result", image(30))

    saved = images.put("result", image(100))

    assert saved.evicted == 1
    assert images.stats().bytes == 100


@pytest.mark.parametrize("limits", [(0, 1, 1), (1, 0, 1), (1, 1, 0)])
def test_rejects_non_positive_limits(limits):
    with pytest.raises(ValueError):
        TemporaryImageStore(*limits)


def test_concurrent_puts_and_gets_keep_counters_consistent():
    images = TemporaryImageStore(ttl_seconds=60, max_items=20, max_bytes=2000)
    ids: list[str] = []
    errors: list[Exception] = []
    start = threading.Barrier(8)

    def worker(index: int) -> None:
        try:
            start.wait()
            for step in range(200):
                saved = images.put("result" if step % 2 else "cutout", image(10 + (index + step) % 90))
                ids.append(saved.image_id)
                images.get("result", ids[(step * 7) % len(ids)])
        except Exception as error:  # surfaced below with the original exception
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    stats = images.stats()
    live = [images._entries[image_id] for image_id in list(images._entries)]
    assert stats.items == len(live) <= 20
    assert stats.bytes == sum(entry.size for entry in live) <= 2000
    assert stats.stored_total == 8 * 200
    assert stats.stored_total - stats.evicted_total - stats.expired_total == stats.items
