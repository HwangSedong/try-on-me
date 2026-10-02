import base64
import binascii
from time import perf_counter
from collections.abc import Sequence

from openai import AsyncOpenAI, BadRequestError, OpenAIError

from app.core.exceptions import ImageGenerationProviderError, InvalidImageGenerationInputError
from app.core.observability import log_event
from app.schemas.generation import GarmentCategory, GarmentInput, ImageAsset
from app.services.image_sizing import generation_size_for, resize_to_source_dimensions

from .base import ImageGenerationProvider

_CATEGORY_ORDER = {
    GarmentCategory.TOP: 0,
    GarmentCategory.BOTTOM: 1,
    GarmentCategory.OUTER: 2,
    GarmentCategory.SHOES: 3,
    GarmentCategory.HAT: 4,
    GarmentCategory.ACCESSORY: 5,
}
_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class OpenAIImageGenerationProvider(ImageGenerationProvider):
    """OpenAI Images API adapter for reference-image virtual try-on editing."""

    def __init__(
        self,
        api_key: str,
        model: str,
        quality: str,
        size: str,
        output_format: str,
        client: AsyncOpenAI | None = None,
    ):
        self.client = client or AsyncOpenAI(api_key=api_key)
        self.model = model
        self.quality = quality
        self.size = size
        self.output_format = output_format

    @staticmethod
    def _ordered_garments(garments: Sequence[GarmentInput]) -> list[GarmentInput]:
        return sorted(garments, key=lambda garment: _CATEGORY_ORDER[garment.category])

    @staticmethod
    def _file_part(image: ImageAsset, filename: str) -> tuple[str, bytes, str]:
        content_type = image.content_type.lower()
        extension = _EXTENSIONS.get(content_type, "png")
        return (f"{filename}.{extension}", image.content, content_type)

    @staticmethod
    def _usage_payload(usage: object | None) -> dict[str, object] | None:
        """Normalize optional SDK usage fields without depending on an SDK version."""
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

    async def generate(
        self,
        person_image: ImageAsset,
        garments: list[GarmentInput],
        prompt: str,
        retry_context: str | None = None,
    ) -> ImageAsset:
        ordered_garments = self._ordered_garments(garments)
        images = [self._file_part(person_image, "person")]
        images.extend(self._file_part(garment.image, garment.category.value) for garment in ordered_garments)
        generation_size = generation_size_for(person_image.width, person_image.height) if person_image.width and person_image.height else self.size
        input_images = [
            {"role": "person", "content_type": person_image.content_type, "bytes": len(person_image.content)},
            *[
                {"role": garment.category.value, "content_type": garment.image.content_type, "bytes": len(garment.image.content)}
                for garment in ordered_garments
            ],
        ]
        started_at = perf_counter()
        log_event(
            "llm.call.started",
            provider="openai",
            operation="images.edit",
            model=self.model,
            quality=self.quality,
            size=generation_size,
            source_size=f"{person_image.width}x{person_image.height}" if person_image.width and person_image.height else None,
            input_images=input_images,
        )

        try:
            response = await self.client.images.edit(
                model=self.model,
                image=images,
                prompt=prompt,
                quality=self.quality,
                size=generation_size,
                output_format=self.output_format,
            )
            encoded_image = response.data[0].b64_json if response.data else None
            if not encoded_image:
                raise ImageGenerationProviderError("OpenAI returned no image data")
            image = ImageAsset(
                content=base64.b64decode(encoded_image, validate=True),
                content_type=f"image/{self.output_format}",
                filename=f"try-on-result.{self.output_format}",
            )
            if person_image.width and person_image.height:
                image = resize_to_source_dimensions(image, person_image.width, person_image.height)
            log_event(
                "llm.call.completed",
                provider="openai",
                operation="images.edit",
                model=self.model,
                duration_ms=round((perf_counter() - started_at) * 1000),
                output_content_type=image.content_type,
                output_bytes=len(image.content),
                output_size=f"{image.width}x{image.height}" if image.width and image.height else None,
                openai_request_id=getattr(response, "_request_id", None),
                usage=self._usage_payload(getattr(response, "usage", None)),
            )
            return image
        except BadRequestError as error:
            log_event("llm.call.failed", provider="openai", operation="images.edit", model=self.model,
                      duration_ms=round((perf_counter() - started_at) * 1000), error_type=type(error).__name__, status_code=getattr(error, "status_code", None))
            raise InvalidImageGenerationInputError("The image edit request was rejected") from error
        except OpenAIError as error:
            log_event("llm.call.failed", provider="openai", operation="images.edit", model=self.model,
                      duration_ms=round((perf_counter() - started_at) * 1000), error_type=type(error).__name__, status_code=getattr(error, "status_code", None))
            raise ImageGenerationProviderError("The image generation service failed") from error
        except ImageGenerationProviderError as error:
            log_event("llm.call.failed", provider="openai", operation="images.edit", model=self.model,
                      duration_ms=round((perf_counter() - started_at) * 1000), error_type=type(error).__name__)
            raise
        except (ValueError, IndexError, binascii.Error) as error:
            log_event("llm.call.failed", provider="openai", operation="images.edit", model=self.model,
                      duration_ms=round((perf_counter() - started_at) * 1000), error_type=type(error).__name__)
            raise ImageGenerationProviderError("The image generation service returned an invalid response") from error
