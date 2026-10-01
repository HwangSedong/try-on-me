from app.core.exceptions import GenerationFailedException
from app.schemas.generation import GarmentInput, GenerationInput, GenerationOutput, ImageAsset
from app.services.background_remover import BackgroundRemover
from app.services.outfit_generator import OutfitGenerator
from app.services.quality_validator import QualityValidator
from app.services.safety_validator import SafetyValidator


class OutfitPipeline:
    def __init__(self, background_remover: BackgroundRemover, generator: OutfitGenerator, safety_validator: SafetyValidator, quality_validator: QualityValidator, max_retries: int = 3):
        self.background_remover = background_remover
        self.generator = generator
        self.safety_validator = safety_validator
        self.quality_validator = quality_validator
        self.max_retries = max_retries

    async def _preprocess(self, request: GenerationInput) -> tuple[ImageAsset, list[GarmentInput]]:
        person = await self.background_remover.remove_background(request.person)
        garments = [GarmentInput(category=item.category, image=await self.background_remover.remove_background(item.image)) for item in request.garments]
        return person, garments

    async def run(self, request: GenerationInput) -> GenerationOutput:
        person, garments = (await self._preprocess(request)) if request.remove_background else (request.person, request.garments)
        retry_context: str | None = None
        for attempt in range(self.max_retries + 1):
            result = await self.generator.generate(person, garments, retry_context)
            safety = await self.safety_validator.validate(result)
            if not safety.safe:
                retry_context = safety.reason or "safety validation failed; ensure the person remains fully clothed"
                continue
            quality = await self.quality_validator.validate(person, garments, result)
            if quality.valid:
                return GenerationOutput(image=result, retry_count=attempt, validation=quality)
            retry_context = "; ".join(quality.issues) or "quality validation failed; apply all requested garments accurately"
        raise GenerationFailedException()

