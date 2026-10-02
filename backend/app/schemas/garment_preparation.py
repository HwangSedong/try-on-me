from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.schemas.generation import GarmentCategory, ImageAsset


@dataclass(frozen=True)
class GarmentPreparation:
    detected_category: GarmentCategory
    confidence: float
    quality: str
    issues: list[str]
    cutout: ImageAsset


class GarmentPreparationResponse(BaseModel):
    detected_category: GarmentCategory
    confidence: float = Field(ge=0, le=1)
    quality: str
    issues: list[str] = Field(default_factory=list)
    cutout_url: str
