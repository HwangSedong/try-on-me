import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from app.schemas.generation import GarmentCategory, ImageAsset
from app.services.garment_preparer import OpenAIGarmentPreparer


def png(width: int = 64, height: int = 96) -> bytes:
    output = BytesIO()
    Image.new("RGBA", (width, height), (255, 255, 255, 0)).save(output, format="PNG")
    return output.getvalue()


class CapturingChat:
    def __init__(self):
        self.request: dict | None = None

    async def create(self, **kwargs):
        self.request = kwargs
        content = '{"category":"outer","confidence":0.93,"quality":"warning","issues":["인물이 함께 있어 가장자리 확인이 필요합니다."]}'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None, _request_id="classify-request")


class CapturingImages:
    def __init__(self):
        self.request: dict | None = None

    async def edit(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png()).decode())], usage=None, _request_id="cutout-request")


@pytest.mark.asyncio
async def test_classifies_then_creates_a_transparent_cutout():
    chat = CapturingChat()
    images = CapturingImages()
    client = SimpleNamespace(chat=SimpleNamespace(completions=chat), images=images)
    preparer = OpenAIGarmentPreparer("not-a-real-key", "gpt-4o-mini", "gpt-image-2.5-sunburst", client=client)

    result = await preparer.prepare(ImageAsset(png(240, 320), "image/png", "reference.png"), GarmentCategory.TOP)

    assert result.detected_category == GarmentCategory.OUTER
    assert result.confidence == 0.93
    assert result.quality == "warning"
    assert result.cutout.content_type == "image/png"
    assert result.cutout.width == 64
    assert result.cutout.height == 96
    assert chat.request["model"] == "gpt-4o-mini"
    assert images.request["model"] == "gpt-image-2.5-sunburst"
    assert images.request["background"] == "transparent"
    assert "Extract only the outer garment" in images.request["prompt"]
