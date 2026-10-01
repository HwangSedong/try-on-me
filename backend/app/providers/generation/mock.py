from app.schemas.generation import GarmentInput, ImageAsset

from .base import ImageGenerationProvider


class MockImageGenerationProvider(ImageGenerationProvider):
    """Development-only provider returning the person image unchanged.

    This is deliberately not a virtual try-on implementation and must never be
    selected for production. Replace it with an image-editing API adapter.
    """

    async def generate(self, person_image: ImageAsset, garments: list[GarmentInput], prompt: str, retry_context: str | None = None) -> ImageAsset:
        return person_image

