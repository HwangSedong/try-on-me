from app.core.exceptions import GenerationFailedException
from app.core.observability import log_event
from app.schemas.generation import GarmentInput, GenerationInput, GenerationOutput, ImageAsset
from app.services.background_remover import BackgroundRemover
from app.services.outfit_generator import OutfitGenerator
from app.services.quality_validator import QualityValidator
from app.services.safety_validator import SafetyValidator
from time import perf_counter


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
        pipeline_started_at = perf_counter()
        log_event("pipeline.started", remove_background=request.remove_background, garment_categories=[item.category.value for item in request.garments])
        preprocessing_started_at = perf_counter()
        person, garments = (await self._preprocess(request)) if request.remove_background else (request.person, request.garments)
        log_event("pipeline.preprocessing.completed", duration_ms=round((perf_counter() - preprocessing_started_at) * 1000))
        retry_context: str | None = None
        for attempt in range(self.max_retries + 1):
            generation_started_at = perf_counter()
            result = await self.generator.generate(person, garments, retry_context)
            log_event("pipeline.generation.completed", attempt=attempt + 1, duration_ms=round((perf_counter() - generation_started_at) * 1000))
            safety_started_at = perf_counter()
            safety = await self.safety_validator.validate(result)
            log_event("pipeline.safety.completed", attempt=attempt + 1, duration_ms=round((perf_counter() - safety_started_at) * 1000), safe=safety.safe)
            if not safety.safe:
                retry_context = safety.reason or "safety validation failed; ensure the person remains fully clothed"
                continue
            quality_started_at = perf_counter()
            quality = await self.quality_validator.validate(person, garments, result)
            log_event("pipeline.quality.completed", attempt=attempt + 1, duration_ms=round((perf_counter() - quality_started_at) * 1000), valid=quality.valid, issues=quality.issues)
            if quality.valid:
                log_event("pipeline.completed", retry_count=attempt, duration_ms=round((perf_counter() - pipeline_started_at) * 1000))
                return GenerationOutput(image=result, retry_count=attempt, validation=quality)
            retry_context = "; ".join(quality.issues) or "quality validation failed; apply all requested garments accurately"
        log_event("pipeline.failed", attempts=self.max_retries + 1, duration_ms=round((perf_counter() - pipeline_started_at) * 1000))
        raise GenerationFailedException()
