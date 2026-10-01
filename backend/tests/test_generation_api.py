from io import BytesIO

from fastapi.testclient import TestClient

from app.main import create_app


client = TestClient(create_app())


def test_requires_person_image():
    response = client.post("/api/generate", files={"top": ("top.png", BytesIO(b"x"), "image/png")})
    assert response.status_code == 422


def test_requires_a_garment():
    response = client.post("/api/generate", files={"person": ("person.png", BytesIO(b"x"), "image/png")})
    assert response.status_code == 422
    assert "fashion item" in response.json()["detail"]


def test_mock_end_to_end_returns_temporary_result():
    response = client.post(
        "/api/generate",
        files={
            "person": ("person.png", BytesIO(b"person-image"), "image/png"),
            "top": ("top.png", BytesIO(b"top-image"), "image/png"),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    image = client.get(payload["result_url"])
    assert image.status_code == 200
    assert image.content == b"person-image"
