from app.schemas.generation import GarmentInput, GarmentValidation, ImageAsset, QualityResult

from .base import VisionValidationProvider


class MockVisionValidationProvider(VisionValidationProvider):
    """Development-only validator; assumes the provider output is acceptable."""

    async def validate(self, source_person: ImageAsset, garments: list[GarmentInput], generated_image: ImageAsset) -> QualityResult:
        checks = {garment.category.value: GarmentValidation(required=True, present=True, match=True) for garment in garments}
        return QualityResult(valid=True, garments=checks)

