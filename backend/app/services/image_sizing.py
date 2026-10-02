"""Image dimension inspection and safe GPT Image output sizing."""

from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.core.exceptions import InvalidImageGenerationInputError
from app.schemas.generation import ImageAsset

_MULTIPLE = 16
_MIN_PIXELS = 655_360
_MAX_PIXELS = 8_294_400
_MAX_EDGE = 3_840
_MIN_ASPECT_RATIO = 1 / 3
_MAX_ASPECT_RATIO = 3
_FORMAT_BY_CONTENT_TYPE = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}


def inspect_dimensions(content: bytes) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            return image.size
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise InvalidImageGenerationInputError("The uploaded file is not a valid image") from error


def generation_size_for(width: int, height: int) -> str:
    """Choose the nearest GPT Image-compatible size while preserving aspect ratio."""
    aspect_ratio = width / height
    if not _MIN_ASPECT_RATIO <= aspect_ratio <= _MAX_ASPECT_RATIO:
        raise InvalidImageGenerationInputError("The source image aspect ratio is outside the supported range")

    pixels = width * height
    scale = 1.0
    if pixels < _MIN_PIXELS:
        scale = (_MIN_PIXELS / pixels) ** 0.5
    if pixels > _MAX_PIXELS:
        scale = (_MAX_PIXELS / pixels) ** 0.5
    if max(width, height) * scale > _MAX_EDGE:
        scale = _MAX_EDGE / max(width, height)

    target_width = max(_MULTIPLE, round(width * scale / _MULTIPLE) * _MULTIPLE)
    target_height = max(_MULTIPLE, round(height * scale / _MULTIPLE) * _MULTIPLE)
    while target_width * target_height > _MAX_PIXELS or max(target_width, target_height) > _MAX_EDGE:
        target_width -= _MULTIPLE
        target_height -= _MULTIPLE
    return f"{target_width}x{target_height}"


def resize_to_source_dimensions(image: ImageAsset, width: int, height: int) -> ImageAsset:
    """Guarantee the final response has the exact dimensions of the user image."""
    try:
        with Image.open(BytesIO(image.content)) as opened:
            source = opened.copy()
        if source.size == (width, height):
            return ImageAsset(image.content, image.content_type, image.filename, width, height)
        if image.content_type == "image/jpeg" and source.mode not in {"RGB", "L"}:
            source = source.convert("RGB")
        resized = source.resize((width, height), Image.Resampling.LANCZOS)
        output = BytesIO()
        resized.save(output, format=_FORMAT_BY_CONTENT_TYPE.get(image.content_type, "PNG"))
        return ImageAsset(output.getvalue(), image.content_type, image.filename, width, height)
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise InvalidImageGenerationInputError("The generated image could not be decoded") from error
