from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app.core.exceptions import GenerationFailedException
from app.pipeline.outfit_pipeline import OutfitPipeline
from app.schemas.generation import GarmentCategory, GarmentInput, GenerateResponse, GenerationInput, ImageAsset

router = APIRouter(prefix="/api", tags=["generation"])
_results: dict[str, ImageAsset] = {}
_categories = [GarmentCategory.TOP, GarmentCategory.BOTTOM, GarmentCategory.OUTER, GarmentCategory.SHOES, GarmentCategory.HAT, GarmentCategory.ACCESSORY]


async def _asset(upload: UploadFile) -> ImageAsset:
    if not upload.content_type or not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail=f"{upload.filename or 'file'} must be an image")
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=422, detail=f"{upload.filename or 'file'} is empty")
    return ImageAsset(content=content, content_type=upload.content_type, filename=upload.filename)


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    request: Request,
    person: UploadFile = File(...),
    top: UploadFile | None = File(None), bottom: UploadFile | None = File(None), outer: UploadFile | None = File(None),
    shoes: UploadFile | None = File(None), hat: UploadFile | None = File(None), accessory: UploadFile | None = File(None),
    remove_background: bool = Form(True),
) -> GenerateResponse:
    uploads = {GarmentCategory.TOP: top, GarmentCategory.BOTTOM: bottom, GarmentCategory.OUTER: outer, GarmentCategory.SHOES: shoes, GarmentCategory.HAT: hat, GarmentCategory.ACCESSORY: accessory}
    garments = [GarmentInput(category=category, image=await _asset(upload)) for category, upload in uploads.items() if upload is not None]
    if not garments:
        raise HTTPException(status_code=422, detail="At least one fashion item is required")
    pipeline: OutfitPipeline = request.app.state.pipeline
    try:
        output = await pipeline.run(GenerationInput(person=await _asset(person), garments=garments, remove_background=remove_background))
    except GenerationFailedException as error:
        raise HTTPException(status_code=422, detail="요청한 패션 아이템을 안정적으로 적용하지 못했습니다. 다른 이미지를 사용해 다시 시도해주세요.") from error
    result_id = str(uuid4())
    _results[result_id] = output.image
    return GenerateResponse(result_url=f"/api/results/{result_id}", retry_count=output.retry_count)


@router.get("/results/{result_id}")
async def get_result(result_id: str) -> Response:
    image = _results.get(result_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return Response(content=image.content, media_type=image.content_type, headers={"Cache-Control": "no-store"})

