from abc import ABC, abstractmethod

from app.schemas.generation import GarmentInput, ImageAsset


class ImageGenerationProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        person_image: ImageAsset,
        garments: list[GarmentInput],
        prompt: str,
        retry_context: str | None = None,
    ) -> ImageAsset: ...

