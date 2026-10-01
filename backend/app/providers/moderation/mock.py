from app.schemas.generation import ImageAsset, SafetyResult

from .base import ModerationProvider


class MockModerationProvider(ModerationProvider):
    """Development-only permissive moderation. Not safe for production."""

    async def validate(self, image: ImageAsset) -> SafetyResult:
        return SafetyResult(safe=True)

