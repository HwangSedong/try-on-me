from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.generation import router as generation_router
from app.core.config import get_settings
from app.core.observability import configure_observability
from app.pipeline.outfit_pipeline import OutfitPipeline
from app.providers.background.mock import MockBackgroundRemovalProvider
from app.providers.generation.mock import MockImageGenerationProvider
from app.providers.generation.openai_provider import OpenAIImageGenerationProvider
from app.providers.moderation.mock import MockModerationProvider
from app.providers.vision.mock import MockVisionValidationProvider
from app.services.background_remover import BackgroundRemover
from app.services.outfit_generator import OutfitGenerator
from app.services.quality_validator import QualityValidator
from app.services.safety_validator import SafetyValidator


def _mock_only(provider_name: str, configured: str, implementation: object) -> object:
    if configured.lower() != "mock":
        raise RuntimeError(
            f"{provider_name} provider '{configured}' is not implemented. "
            "Configure 'mock' for local development or add a provider adapter."
        )
    return implementation


def create_generation_provider(settings):
    provider = settings.image_generation_provider.lower()
    if provider == "mock":
        return MockImageGenerationProvider()
    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when IMAGE_GENERATION_PROVIDER=openai")
        return OpenAIImageGenerationProvider(
            api_key=settings.openai_api_key,
            model=settings.image_generation_model,
            quality=settings.image_generation_quality,
            size=settings.image_generation_size,
            output_format=settings.image_generation_format,
        )
    raise RuntimeError(f"image generation provider '{settings.image_generation_provider}' is not implemented")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_observability(settings.log_level)
    app = FastAPI(title="Try-On-Me v2 API", version="2.0.0")
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    # Each configured provider is resolved at this boundary, keeping provider SDKs out of routes and pipeline logic.
    app.state.pipeline = OutfitPipeline(
        BackgroundRemover(_mock_only("background removal", settings.background_removal_provider, MockBackgroundRemovalProvider())),  # type: ignore[arg-type]
        OutfitGenerator(create_generation_provider(settings)),
        SafetyValidator(_mock_only("moderation", settings.moderation_provider, MockModerationProvider())),  # type: ignore[arg-type]
        QualityValidator(_mock_only("vision", settings.vision_provider, MockVisionValidationProvider())),  # type: ignore[arg-type]
        max_retries=settings.max_generation_retries,
    )
    app.include_router(generation_router)
    return app


app = create_app()
