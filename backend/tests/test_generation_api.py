from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.providers.generation.mock import MockImageGenerationProvider


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
