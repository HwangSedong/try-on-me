"""Benchmark-only wrapper around the real FastAPI app.

It imports the backend found at --backend-dir (the current tree or a pre-change
checkout), swaps the image generation provider and garment preparer for fakes
that return fixed-size bytes, and adds a /__bench/stats route.  Every other part
of the request path (upload validation, pipeline, result storage, routes) is the
backend's own code, so the same workload can be replayed against both versions.

This measures backend processing and result storage, not image model quality or
OpenAI latency.  No network calls are made.
"""

import argparse
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path


def _offline_environment(log_level: str) -> None:
    # Environment variables take precedence over any backend/.env file.
    os.environ.update({
        "IMAGE_GENERATION_PROVIDER": "mock",
        "GARMENT_PREPARATION_PROVIDER": "mock",
        "VISION_PROVIDER": "mock",
        "BACKGROUND_REMOVAL_PROVIDER": "mock",
        "MODERATION_PROVIDER": "mock",
        "OPENAI_API_KEY": "",
        "MAX_GENERATION_RETRIES": "3",
        "LOG_LEVEL": log_level,
    })


def _read_kib_fields(path: str, fields: set[str]) -> dict[str, int]:
    values: dict[str, int] = {}
    with open(path, encoding="ascii") as status:
        for line in status:
            name, _, rest = line.partition(":")
            if name in fields:
                values[name] = int(rest.split()[0]) * 1024
    return values


def _read_int(path: str) -> int | None:
    try:
        raw = Path(path).read_text(encoding="ascii").strip()
    except OSError:
        return None
    return None if raw == "max" else int(raw)


def process_memory() -> dict[str, int | None]:
    if Path("/proc/self/status").exists():
        values = _read_kib_fields("/proc/self/status", {"VmRSS", "VmHWM"})
        return {"rss_bytes": values.get("VmRSS"), "peak_rss_bytes": values.get("VmHWM")}
    import psutil

    info = psutil.Process().memory_info()
    return {"rss_bytes": info.rss, "peak_rss_bytes": getattr(info, "peak_wset", None)}


def cgroup_memory() -> dict[str, int | None]:
    events: dict[str, int] = {}
    try:
        for line in Path("/sys/fs/cgroup/memory.events").read_text(encoding="ascii").splitlines():
            name, value = line.split()
            events[name] = int(value)
    except OSError:
        pass
    return {
        "current_bytes": _read_int("/sys/fs/cgroup/memory.current"),
        "peak_bytes": _read_int("/sys/fs/cgroup/memory.peak"),
        "max_bytes": _read_int("/sys/fs/cgroup/memory.max"),
        "oom_kill_events": events.get("oom_kill"),
    }


def store_stats(app) -> dict[str, object]:
    generation_module = sys.modules["app.api.generation"]
    # Pre-change backend: two unbounded module-level dictionaries.
    if hasattr(generation_module, "_results"):
        stores = [generation_module._results, generation_module._cutouts]
        return {
            "implementation": "unbounded-dict",
            "items": sum(len(store) for store in stores),
            "bytes": sum(len(asset.content) for store in stores for asset in store.values()),
        }
    stats = app.state.image_store.stats()
    return {"implementation": "temporary-image-store", **(asdict(stats) if is_dataclass(stats) else dict(stats))}


def install_fakes(app, result_bytes: int, cutout_bytes: int) -> None:
    from app.schemas.garment_preparation import GarmentPreparation
    from app.schemas.generation import ImageAsset

    result_template = os.urandom(result_bytes)
    cutout_template = os.urandom(cutout_bytes)

    class FixedSizeResultProvider:
        """Returns a new result buffer per call, like a decoded provider response."""

        async def generate(self, person_image, garments, prompt, retry_context=None):
            return ImageAsset(memoryview(result_template).tobytes(), "image/png", None, person_image.width, person_image.height)

    class FixedSizeCutoutPreparer:
        async def prepare(self, image, requested_category):
            cutout = ImageAsset(memoryview(cutout_template).tobytes(), "image/png", None, 1024, 1024)
            return GarmentPreparation(requested_category, 1.0, "good", [], cutout)

    app.state.pipeline.generator.provider = FixedSizeResultProvider()
    app.state.garment_preparer = FixedSizeCutoutPreparer()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-dir", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--result-bytes", type=int, required=True)
    parser.add_argument("--cutout-bytes", type=int, required=True)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    _offline_environment(args.log_level)
    sys.path.insert(0, str(Path(args.backend_dir).resolve()))

    import uvicorn
    from app.main import app

    install_fakes(app, args.result_bytes, args.cutout_bytes)

    async def stats() -> dict[str, object]:
        return {"process": process_memory(), "cgroup": cgroup_memory(), "store": store_stats(app)}

    app.add_api_route("/__bench/stats", stats, methods=["GET"])
    uvicorn.run(app, host=args.host, port=args.port, workers=1, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
