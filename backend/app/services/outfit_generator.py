from app.providers.generation.base import ImageGenerationProvider
from app.schemas.generation import GarmentInput, ImageAsset


class OutfitGenerator:
    def __init__(self, provider: ImageGenerationProvider):
        self.provider = provider

    async def generate(self, person_image: ImageAsset, garments: list[GarmentInput], retry_context: str | None = None) -> ImageAsset:
        ordered_garments = sorted(garments, key=lambda garment: ("top", "bottom", "outer", "shoes", "hat", "accessory").index(garment.category.value))
        reference_roles = ["Image 1: SOURCE PERSON photograph — the exact person and scene to edit."]
        reference_roles.extend(
            f"Image {index}: {garment.category.value.upper()} garment reference — apply only this garment category."
            for index, garment in enumerate(ordered_garments, start=2)
        )
        prompt = (
            "Edit Image 1, do not create a new person or a new scene. Create a photorealistic full-body "
            "virtual try-on result. Preserve the exact same person's face identity, hairstyle, skin tone, "
            "body proportions, pose, camera angle, hands, feet, lighting, and background unless naturally "
            "occluded by the requested garment. Apply only the requested garments from the reference images. "
            "For each garment, preserve its color, fabric/material, pattern, silhouette, collar shape, sleeve "
            "length, visible logos, buttons, zippers, and other distinctive details. Place top garments on the "
            "upper body, bottoms on the lower body, outerwear naturally over the top, shoes on the feet, hats "
            "on the head, and accessories in their natural position. Use realistic layering, fabric deformation, "
            "occlusion, shadows, and lighting. Do not change or invent any unrequested garment category; retain "
            "the source person's original clothing in all categories without a reference. Keep the person fully "
            "and appropriately clothed.\n\nReference image roles:\n"
            + "\n".join(reference_roles)
        )
        if retry_context:
            prompt += (
                "\n\nPrevious attempt issue: " + retry_context + ". Correct only this issue while preserving the "
                "person identity, source scene, and all successfully applied garments."
            )
        return await self.provider.generate(person_image, ordered_garments, prompt, retry_context)
