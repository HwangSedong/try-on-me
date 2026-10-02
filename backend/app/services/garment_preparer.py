import base64
import binascii
import json
from time import perf_counter

from openai import AsyncOpenAI, OpenAIError

from app.core.exceptions import ImageGenerationProviderError, InvalidImageGenerationInputError
from app.core.observability import log_event
from app.schemas.garment_preparation import GarmentPreparation
from app.schemas.generation import GarmentCategory, ImageAsset
from app.services.image_sizing import inspect_dimensions

_CATEGORY_VALUES = {category.value for category in GarmentCategory}
_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class GarmentPreparer:
    async def prepare(self, image: ImageAsset, requested_category: GarmentCategory) -> GarmentPreparation:
        raise NotImplementedError


class MockGarmentPreparer(GarmentPreparer):
    """Offline fallback: keeps the original file and clearly marks it for review."""

    async def prepare(self, image: ImageAsset, requested_category: GarmentCategory) -> GarmentPreparation:
        return GarmentPreparation(
            detected_category=requested_category,
            confidence=0.5,
            quality="warning",
            issues=["자동 컷아웃은 실제 OpenAI 또는 분할 모델 제공자에서 사용할 수 있습니다."],
            cutout=image,
        )


class OpenAIGarmentPreparer(GarmentPreparer):
    """Classifies an uploaded reference and returns a transparent garment cutout."""

    def __init__(self, api_key: str, classification_model: str, cutout_model: str, client: AsyncOpenAI | None = None):
        self.client = client or AsyncOpenAI(api_key=api_key)
        self.classification_model = classification_model
        self.cutout_model = cutout_model

    @staticmethod
    def _file_part(image: ImageAsset) -> tuple[str, bytes, str]:
        extension = _EXTENSIONS.get(image.content_type, "png")
        return (f"garment-reference.{extension}", image.content, image.content_type)

    @staticmethod
    def _usage_payload(usage: object | None) -> dict[str, object] | None:
        if usage is None:
            return None

        def value(source: object, field: str) -> object | None:
            return source.get(field) if isinstance(source, dict) else getattr(source, field, None)

        input_details = value(usage, "input_tokens_details")
        output_details = value(usage, "output_tokens_details")
        payload = {
            "input_tokens": value(usage, "input_tokens"),
            "output_tokens": value(usage, "output_tokens"),
            "total_tokens": value(usage, "total_tokens"),
            "input_image_tokens": value(input_details, "image_tokens") if input_details else None,
            "input_text_tokens": value(input_details, "text_tokens") if input_details else None,
            "output_image_tokens": value(output_details, "image_tokens") if output_details else None,
        }
        return {key: item for key, item in payload.items() if item is not None} or None

    async def _classify(self, image: ImageAsset) -> tuple[GarmentCategory, float, str, list[str]]:
        encoded = base64.b64encode(image.content).decode("ascii")
        started_at = perf_counter()
        prompt = """Inspect this fashion reference image. Return JSON only with keys: category, confidence, quality, issues.
category must be exactly one of top, bottom, outer, shoes, hat, accessory. Select the most visually dominant wearable item.
confidence is a number from 0 to 1. quality must be one of good, warning, poor based on whether the dominant garment can be isolated faithfully for virtual try-on.
issues is a short Korean array. Mark warning or poor for multiple people, major occlusion, multiple competing garments, a large background object, or hidden garment details."""
        try:
            log_event(
                "llm.call.started",
                provider="openai", operation="chat.completions.classify_garment", model=self.classification_model,
                quality="low-detail vision", size="source image",
                input_images=[{"role": "garment reference", "content_type": image.content_type, "bytes": len(image.content)}],
            )
            response = await self.client.chat.completions.create(
                model=self.classification_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{image.content_type};base64,{encoded}", "detail": "low"}},
                ]}],
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            category = payload.get("category")
            if category not in _CATEGORY_VALUES:
                raise ValueError("unsupported garment category")
            confidence = min(1.0, max(0.0, float(payload.get("confidence", 0))))
            quality = payload.get("quality") if payload.get("quality") in {"good", "warning", "poor"} else "warning"
            issues = [str(issue) for issue in payload.get("issues", [])][:4]
            log_event(
                "llm.call.completed",
                provider="openai", operation="chat.completions.classify_garment", model=self.classification_model,
                duration_ms=round((perf_counter() - started_at) * 1000), output_content_type="application/json",
                output_bytes=len(response.choices[0].message.content or ""), openai_request_id=getattr(response, "_request_id", None),
                usage=self._usage_payload(getattr(response, "usage", None)),
            )
            return GarmentCategory(category), confidence, quality, issues
        except (OpenAIError, ValueError, TypeError, json.JSONDecodeError) as error:
            log_event(
                "llm.call.failed", provider="openai", operation="chat.completions.classify_garment", model=self.classification_model,
                duration_ms=round((perf_counter() - started_at) * 1000), error_type=type(error).__name__,
            )
            raise ImageGenerationProviderError("The garment could not be classified") from error

    async def prepare(self, image: ImageAsset, requested_category: GarmentCategory) -> GarmentPreparation:
        started_at = perf_counter()
        log_event("garment.preparation.started", requested_category=requested_category.value, input_bytes=len(image.content), input_content_type=image.content_type)
        category, confidence, quality, issues = await self._classify(image)
        prompt = (
            f"Extract only the {category.value} garment from this fashion reference image. "
            "Remove every person, face, body part, hair, accessories not belonging to the garment, background, text, and scenery. "
            "Return the garment centered on a fully transparent background as a clean PNG cutout. "
            "Preserve the garment's exact color, silhouette, stitching, pattern, material, hardware, and visible labels. "
            "Do not invent missing details, restyle the garment, add a mannequin, or add a shadow."
        )
        cutout_started_at = perf_counter()
        try:
            log_event(
                "llm.call.started",
                provider="openai", operation="images.edit.garment_cutout", model=self.cutout_model, quality="medium", size="1024x1024",
                input_images=[{"role": "garment reference", "content_type": image.content_type, "bytes": len(image.content)}],
            )
            response = await self.client.images.edit(
                model=self.cutout_model,
                image=self._file_part(image),
                prompt=prompt,
                quality="medium",
                size="1024x1024",
                output_format="png",
                background="transparent",
            )
            encoded = response.data[0].b64_json if response.data else None
            if not encoded:
                raise ImageGenerationProviderError("OpenAI returned no garment cutout")
            content = base64.b64decode(encoded, validate=True)
            width, height = inspect_dimensions(content)
            cutout = ImageAsset(content=content, content_type="image/png", filename="garment-cutout.png", width=width, height=height)
            log_event(
                "llm.call.completed", provider="openai", operation="images.edit.garment_cutout", model=self.cutout_model,
                duration_ms=round((perf_counter() - cutout_started_at) * 1000), output_content_type="image/png",
                output_bytes=len(content), output_size=f"{width}x{height}", openai_request_id=getattr(response, "_request_id", None),
                usage=self._usage_payload(getattr(response, "usage", None)),
            )
            log_event("garment.preparation.completed", detected_category=category.value, confidence=confidence, quality=quality, duration_ms=round((perf_counter() - started_at) * 1000), output_size=f"{width}x{height}")
            return GarmentPreparation(category, confidence, quality, issues, cutout)
        except OpenAIError as error:
            log_event("llm.call.failed", provider="openai", operation="images.edit.garment_cutout", model=self.cutout_model, duration_ms=round((perf_counter() - cutout_started_at) * 1000), error_type=type(error).__name__)
            log_event("garment.preparation.failed", error_type=type(error).__name__, duration_ms=round((perf_counter() - started_at) * 1000))
            raise ImageGenerationProviderError("The garment cutout could not be created") from error
        except (ValueError, IndexError, binascii.Error) as error:
            log_event("llm.call.failed", provider="openai", operation="images.edit.garment_cutout", model=self.cutout_model, duration_ms=round((perf_counter() - cutout_started_at) * 1000), error_type=type(error).__name__)
            log_event("garment.preparation.failed", error_type=type(error).__name__, duration_ms=round((perf_counter() - started_at) * 1000))
            raise InvalidImageGenerationInputError("The garment cutout was invalid") from error
