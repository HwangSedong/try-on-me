from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GarmentCategory(str, Enum):
    TOP = "top"
    BOTTOM = "bottom"
    OUTER = "outer"
    SHOES = "shoes"
    HAT = "hat"
    ACCESSORY = "accessory"


@dataclass(frozen=True)
class ImageAsset:
    content: bytes
    content_type: str
    filename: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class GarmentInput:
    category: GarmentCategory
    image: ImageAsset


@dataclass(frozen=True)
class GenerationInput:
    person: ImageAsset
    garments: list[GarmentInput]
    remove_background: bool = True


class SafetyResult(BaseModel):
    safe: bool
    reason: str | None = None


class GarmentValidation(BaseModel):
    required: bool
    present: bool
    match: bool


class QualityResult(BaseModel):
    valid: bool
    person_preserved: bool = True
    anatomy_valid: bool = True
    fully_clothed: bool = True
    garments: dict[str, GarmentValidation] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)


class GenerationOutput(BaseModel):
    image: ImageAsset
    retry_count: int
    validation: QualityResult

    model_config = {"arbitrary_types_allowed": True}


class GenerateResponse(BaseModel):
    status: str = "completed"
    result_url: str
    retry_count: int


class ErrorResponse(BaseModel):
    status: str = "failed"
    message: str
    details: dict[str, Any] | None = None
