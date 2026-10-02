import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from openai import OpenAIError
from PIL import Image

from app.core.exceptions import ImageGenerationProviderError
from app.providers.generation.openai_provider import OpenAIImageGenerationProvider
from app.schemas.generation import GarmentCategory, GarmentInput, ImageAsset
from app.services.outfit_generator import OutfitGenerator


def asset(value: bytes, content_type: str = "image/png") -> ImageAsset:
    return ImageAsset(content=value, content_type=content_type)


def png(width: int, height: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="PNG")
    return output.getvalue()


class CapturingImages:
    def __init__(self, encoded_result: str | None = None, error: Exception | None = None, usage=None):
        self.encoded_result = encoded_result
        self.error = error
        self.usage = usage
        self.request: dict | None = None

    async def edit(self, **kwargs):
        self.request = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(data=[SimpleNamespace(b64_json=self.encoded_result)], usage=self.usage, _request_id="req_observed")


class CapturingClient:
    def __init__(self, images: CapturingImages):
        self.images = images


def provider(images: CapturingImages) -> OpenAIImageGenerationProvider:
    return OpenAIImageGenerationProvider(
        api_key="not-a-real-key",
        model="gpt-image-2.5-sunburst",
        quality="high",
        size="1024x1536",
        output_format="png",
        client=CapturingClient(images),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_orders_person_then_garments_for_openai_edit():
    images = CapturingImages(base64.b64encode(b"generated-image").decode())
    generator = OutfitGenerator(provider(images))
    garments = [
        GarmentInput(GarmentCategory.SHOES, asset(b"shoes")),
        GarmentInput(GarmentCategory.TOP, asset(b"top")),
        GarmentInput(GarmentCategory.HAT, asset(b"hat")),
        GarmentInput(GarmentCategory.BOTTOM, asset(b"bottom")),
        GarmentInput(GarmentCategory.OUTER, asset(b"outer")),
        GarmentInput(GarmentCategory.ACCESSORY, asset(b"accessory")),
    ]

    result = await generator.generate(asset(b"person"), garments)

    assert result.content == b"generated-image"
    assert [file_part[0] for file_part in images.request["image"]] == [
        "person.png", "top.png", "bottom.png", "outer.png", "shoes.png", "hat.png", "accessory.png",
    ]
    assert images.request["model"] == "gpt-image-2.5-sunburst"
    assert images.request["output_format"] == "png"
    assert "Image 2: TOP garment reference" in images.request["prompt"]
    assert "Image 7: ACCESSORY garment reference" in images.request["prompt"]


@pytest.mark.asyncio
async def test_decodes_openai_base64_into_image_asset():
    images = CapturingImages(base64.b64encode(b"decoded-png").decode())

    result = await provider(images).generate(asset(b"person"), [GarmentInput(GarmentCategory.TOP, asset(b"top"))], "edit")

    assert result.content == b"decoded-png"
    assert result.content_type == "image/png"
    assert result.filename == "try-on-result.png"


@pytest.mark.asyncio
async def test_uses_source_aspect_ratio_and_returns_the_exact_source_dimensions():
    generated = png(640, 864)
    images = CapturingImages(base64.b64encode(generated).decode())
    person = ImageAsset(png(1200, 1600), "image/png", width=1200, height=1600)

    result = await provider(images).generate(person, [GarmentInput(GarmentCategory.TOP, asset(png(100, 100)))], "edit")

    assert images.request["size"] == "1200x1600"
    with Image.open(BytesIO(result.content)) as output:
        assert output.size == (1200, 1600)
    assert result.width == 1200
    assert result.height == 1600


@pytest.mark.asyncio
async def test_logs_model_duration_and_token_usage_for_each_openai_call(caplog):
    usage = SimpleNamespace(
        input_tokens=21,
        output_tokens=34,
        total_tokens=55,
        input_tokens_details=SimpleNamespace(image_tokens=18, text_tokens=3),
        output_tokens_details=SimpleNamespace(image_tokens=34),
    )
    images = CapturingImages(base64.b64encode(b"result").decode(), usage=usage)

    with caplog.at_level("INFO", logger="try_on_me.observability"):
        await provider(images).generate(asset(b"person"), [GarmentInput(GarmentCategory.TOP, asset(b"top"))], "edit")

    events = [record.event_data for record in caplog.records if record.name == "try_on_me.observability"]
    completed = next(event for event in events if event["event"] == "llm.call.completed")
    assert "OpenAI 이미지 생성 완료" in caplog.text
    assert completed["model"] == "gpt-image-2.5-sunburst"
    assert completed["duration_ms"] >= 0
    assert completed["openai_request_id"] == "req_observed"
    assert completed["usage"] == {
        "input_tokens": 21,
        "output_tokens": 34,
        "total_tokens": 55,
        "input_image_tokens": 18,
        "input_text_tokens": 3,
        "output_image_tokens": 34,
    }


@pytest.mark.asyncio
async def test_wraps_openai_provider_errors_without_exposing_details():
    images = CapturingImages(error=OpenAIError("provider unavailable"))

    with pytest.raises(ImageGenerationProviderError):
        await provider(images).generate(asset(b"person"), [GarmentInput(GarmentCategory.TOP, asset(b"top"))], "edit")
