from app.providers.vision.base import VisionValidationProvider
from app.schemas.generation import GarmentInput, ImageAsset, QualityResult


class QualityValidator:
    def __init__(self, provider: VisionValidationProvider):
        self.provider = provider

    async def validate(self, source_person: ImageAsset, garments: list[GarmentInput], generated_image: ImageAsset) -> QualityResult:
        return await self.provider.validate(source_person, garments, generated_image)

