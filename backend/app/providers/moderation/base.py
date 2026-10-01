from abc import ABC, abstractmethod

from app.schemas.generation import ImageAsset, SafetyResult


class ModerationProvider(ABC):
    @abstractmethod
    async def validate(self, image: ImageAsset) -> SafetyResult: ...

