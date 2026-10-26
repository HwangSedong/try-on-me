import asyncio
import logging
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings
from app.core.exceptions import ImageGenerationProviderError
from app.main import create_app
from app.providers.generation.mock import MockImageGenerationProvider
from app.schemas.generation import ImageAsset, QualityResult
from app.services.garment_preparer import MockGarmentPreparer
from app.services.quality_validator import QualityValidator
from app.services.temporary_image_store import TemporaryImageStore


client = TestClient(create_app())


def png(width: int = 20, height: int = 30) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="PNG")
    return output.getvalue()


def test_requires_person_image():
    response = client.post("/api/generate", files={"top": ("top.png", BytesIO(b"x"), "image/png")})
    assert response.status_code == 422


def test_requires_a_garment():
    response = client.post("/api/generate", files={"person": ("person.png", BytesIO(png()), "image/png")})
    assert response.status_code == 422
    assert "fashion item" in response.json()["detail"]


def test_rejects_unsupported_image_type():
    response = client.post(
        "/api/generate",
        files={
            "person": ("person.gif", BytesIO(b"x"), "image/gif"),
            "top": ("top.png", BytesIO(b"x"), "image/png"),
        },
    )
    assert response.status_code == 422


def test_mock_end_to_end_returns_temporary_result():
    # Keep this endpoint test offline even when a developer's local .env selects OpenAI.
    client.app.state.pipeline.generator.provider = MockImageGenerationProvider()
    response = client.post(
        "/api/generate",
        files={
            "person": ("person.png", BytesIO(png()), "image/png"),
            "top": ("top.png", BytesIO(png()), "image/png"),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    image = client.get(payload["result_url"])
    assert image.status_code == 200
    with Image.open(BytesIO(image.content)) as output:
        assert output.size == (20, 30)


def test_prepares_garment_and_serves_cutout_without_network():
    client.app.state.garment_preparer = MockGarmentPreparer()
    response = client.post(
        "/api/garments/prepare",
        files={"image": ("coat.png", BytesIO(png(80, 120)), "image/png")},
        data={"requested_category": "outer"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detected_category"] == "outer"
    assert payload["quality"] == "warning"
    cutout = client.get(payload["cutout_url"])
    assert cutout.status_code == 200
    with Image.open(BytesIO(cutout.content)) as output:
        assert output.size == (80, 120)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FixedResultProvider:
    def __init__(self, size: int = 64):
        self.size = size

    async def generate(self, person_image, garments, prompt, retry_context=None):
        return ImageAsset(b"r" * self.size, "image/png", None, person_image.width, person_image.height)


class FailingProvider:
    async def generate(self, person_image, garments, prompt, retry_context=None):
        raise ImageGenerationProviderError("upstream unavailable")


class RejectingQuality:
    def __init__(self):
        self.calls = 0

    async def validate(self, source_person, garments, generated_image):
        self.calls += 1
        return QualityResult(valid=False, issues=["top_missing"])


def offline_app(provider=None, store: TemporaryImageStore | None = None):
    app = create_app()
    app.state.pipeline.generator.provider = provider or FixedResultProvider()
    app.state.garment_preparer = MockGarmentPreparer()
    if store is not None:
        app.state.image_store = store
    return app


def generate_files(person: bytes | None = None, content_type: str = "image/png") -> dict:
    return {
        "person": ("person.png", BytesIO(png() if person is None else person), content_type),
        "top": ("top.png", BytesIO(png()), "image/png"),
    }


def test_rejects_empty_image():
    response = TestClient(offline_app()).post("/api/generate", files=generate_files(b""))
    assert response.status_code == 422
    assert "empty" in response.json()["detail"]


def test_rejects_bytes_that_are_not_an_image():
    response = TestClient(offline_app()).post("/api/generate", files=generate_files(b"not an image"))
    assert response.status_code == 422


def test_rejects_upload_over_the_size_limit():
    app = offline_app()
    app.state.settings = Settings(max_upload_size_mb=1)
    response = TestClient(app).post("/api/generate", files=generate_files(b"x" * (1024 * 1024 + 1)))
    assert response.status_code == 413


def test_provider_failure_returns_502_and_stores_nothing():
    app = offline_app(provider=FailingProvider())
    response = TestClient(app).post("/api/generate", files=generate_files())
    assert response.status_code == 502
    assert app.state.image_store.stats().items == 0


def test_exhausted_quality_retries_return_422():
    app = offline_app()
    quality = RejectingQuality()
    app.state.pipeline.quality_validator = QualityValidator(quality)
    response = TestClient(app).post("/api/generate", files=generate_files())
    assert response.status_code == 422
    assert quality.calls == app.state.settings.max_generation_retries + 1


def test_expired_result_returns_404():
    clock = Clock()
    client = TestClient(offline_app(store=TemporaryImageStore(ttl_seconds=60, max_items=10, max_bytes=10_000, clock=clock)))
    result_url = client.post("/api/generate", files=generate_files()).json()["result_url"]
    assert client.get(result_url).status_code == 200

    clock.now += 60
    response = client.get(result_url)
    assert response.status_code == 404
    assert response.json()["detail"] == "Result not found or expired"


def test_evicted_result_returns_404_while_newer_result_is_served():
    client = TestClient(offline_app(store=TemporaryImageStore(ttl_seconds=60, max_items=1, max_bytes=10_000)))
    first = client.post("/api/generate", files=generate_files()).json()["result_url"]
    second = client.post("/api/generate", files=generate_files()).json()["result_url"]

    assert client.get(first).status_code == 404
    assert client.get(second).status_code == 200


def test_result_larger_than_store_budget_returns_507():
    app = offline_app(provider=FixedResultProvider(size=2_000), store=TemporaryImageStore(ttl_seconds=60, max_items=10, max_bytes=1_000))
    response = TestClient(app).post("/api/generate", files=generate_files())
    assert response.status_code == 507
    assert app.state.image_store.stats().rejected_total == 1


def test_cutout_ids_are_not_served_as_results():
    client = TestClient(offline_app())
    cutout_url = client.post(
        "/api/garments/prepare",
        files={"image": ("coat.png", BytesIO(png()), "image/png")},
        data={"requested_category": "outer"},
    ).json()["cutout_url"]
    assert client.get(cutout_url.replace("/cutouts/", "/results/")).status_code == 404


@pytest.mark.asyncio
async def test_concurrent_generations_each_get_their_own_result():
    app = offline_app(store=TemporaryImageStore(ttl_seconds=60, max_items=100, max_bytes=1_000_000))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(*(client.post("/api/generate", files=generate_files()) for _ in range(20)))
        urls = [response.json()["result_url"] for response in responses]
        results = await asyncio.gather(*(client.get(url) for url in urls))

    assert [response.status_code for response in responses] == [200] * 20
    assert len(set(urls)) == 20
    assert all(result.status_code == 200 for result in results)
    assert app.state.image_store.stats().items == 20


def test_completion_log_records_stage_timings_and_store_usage_without_file_names(caplog):
    client = TestClient(offline_app())
    with caplog.at_level("INFO", logger="try_on_me.observability"):
        response = client.post("/api/generate", files=generate_files())
    assert response.status_code == 200

    events = [record.event_data for record in caplog.records if record.name == "try_on_me.observability"]
    completed = next(event for event in events if event["event"] == "generation.request_completed")
    assert set(completed["stage_ms"]) == {"upload", "preprocessing", "generation", "safety", "quality", "store"}
    assert completed["output"] == {"content_type": "image/png", "bytes": 64, "size": "20x30"}
    assert completed["store"]["items"] == 1
    assert "person.png" not in caplog.text and "top.png" not in caplog.text


def test_observability_events_have_an_output_handler():
    create_app()
    assert logging.getLogger("try_on_me.observability").handlers
