from .base import BackgroundRemovalProvider


class MockBackgroundRemovalProvider(BackgroundRemovalProvider):
    """Development-only passthrough. It does not remove backgrounds."""

    async def remove_background(self, image: bytes) -> bytes:
        return image

