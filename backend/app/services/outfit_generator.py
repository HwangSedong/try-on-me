from app.providers.generation.base import ImageGenerationProvider
from app.schemas.generation import GarmentInput, ImageAsset


class OutfitGenerator:
    def __init__(self, provider: ImageGenerationProvider):
        self.provider = provider

    async def generate(self, person_image: ImageAsset, garments: list[GarmentInput], retry_context: str | None = None) -> ImageAsset:
        categories = ", ".join(garment.category.value for garment in garments)
        prompt = (
            "Create a photorealistic full-body fashion photograph. Preserve the person's face, "
            "identity, body proportions, and pose. Apply these reference garments by category: "
            f"{categories}. Preserve each garment's color, material, pattern, logos and design. "
            "Use natural layering, occlusion, fabric deformation, shadows, and lighting. "
            "Keep the person appropriately and fully clothed; do not add substitute garments."
        )
        if retry_context:
            prompt += f" Previous attempt failed: {retry_context}. Correct this while preserving successful details."
        return await self.provider.generate(person_image, garments, prompt, retry_context)

