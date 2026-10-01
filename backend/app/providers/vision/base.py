from abc import ABC, abstractmethod

from app.schemas.generation import GarmentInput, ImageAsset, QualityResult


class VisionValidationProvider(ABC):
    @abstractmethod
    async def validate(self, source_person: ImageAsset, garments: list[GarmentInput], generated_image: ImageAsset) -> QualityResult: ...

