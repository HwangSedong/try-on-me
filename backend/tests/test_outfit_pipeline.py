import pytest

from app.core.exceptions import GenerationFailedException
from app.pipeline.outfit_pipeline import OutfitPipeline
from app.schemas.generation import (
    GarmentCategory, GarmentInput, GarmentValidation, GenerationInput, ImageAsset,
    QualityResult, SafetyResult,
)
from app.services.background_remover import BackgroundRemover
from app.services.outfit_generator import OutfitGenerator
from app.services.quality_validator import QualityValidator
from app.services.safety_validator import SafetyValidator


IMAGE = ImageAsset(b"image", "image/png")
REQUEST = GenerationInput(IMAGE, [GarmentInput(GarmentCategory.TOP, IMAGE)])


class Background:
    async def remove_background(self, image: bytes) -> bytes: return image


class Generator:
    def __init__(self): self.calls = 0
    async def generate(self, person_image, garments, prompt, retry_context=None):
        self.calls += 1
        return person_image


class Safety:
    def __init__(self, results): self.results = iter(results)
    async def validate(self, image): return next(self.results)


class Quality:
    def __init__(self, results): self.results = iter(results)
    async def validate(self, source_person, garments, generated_image): return next(self.results)


def quality(valid: bool, issues: list[str] | None = None) -> QualityResult:
    return QualityResult(valid=valid, garments={"top": GarmentValidation(required=True, present=valid, match=valid)}, issues=issues or [])


def pipeline(safety, quality_validator, retries=3):
    return OutfitPipeline(BackgroundRemover(Background()), OutfitGenerator(Generator()), SafetyValidator(safety), QualityValidator(quality_validator), retries)


@pytest.mark.asyncio
async def test_first_generation_succeeds():
    result = await pipeline(Safety([SafetyResult(safe=True)]), Quality([quality(True)])).run(REQUEST)
    assert result.retry_count == 0


@pytest.mark.asyncio
async def test_safety_failure_retries_then_succeeds():
    result = await pipeline(Safety([SafetyResult(safe=False, reason="exposure"), SafetyResult(safe=True)]), Quality([quality(True)])).run(REQUEST)
    assert result.retry_count == 1


@pytest.mark.asyncio
async def test_garment_validation_failure_retries_then_succeeds():
    result = await pipeline(Safety([SafetyResult(safe=True), SafetyResult(safe=True)]), Quality([quality(False, ["top_missing"]), quality(True)])).run(REQUEST)
    assert result.retry_count == 1


@pytest.mark.asyncio
async def test_maximum_retry_is_enforced():
    with pytest.raises(GenerationFailedException):
        await pipeline(Safety([SafetyResult(safe=False)] * 3), Quality([]), retries=2).run(REQUEST)

