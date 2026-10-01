from app.providers.moderation.base import ModerationProvider
from app.schemas.generation import ImageAsset, SafetyResult


class SafetyValidator:
    def __init__(self, provider: ModerationProvider):
        self.provider = provider

    async def validate(self, image: ImageAsset) -> SafetyResult:
        return await self.provider.validate(image)

