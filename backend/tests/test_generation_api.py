from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.providers.generation.mock import MockImageGenerationProvider
from app.services.garment_preparer import MockGarmentPreparer


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
