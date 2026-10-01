from app.providers.background.base import BackgroundRemovalProvider
from app.schemas.generation import ImageAsset


class BackgroundRemover:
    def __init__(self, provider: BackgroundRemovalProvider):
        self.provider = provider

    async def remove_background(self, image: ImageAsset) -> ImageAsset:
        return ImageAsset(
            content=await self.provider.remove_background(image.content),
            content_type=image.content_type,
            filename=image.filename,
        )

