from uuid import uuid4
from time import perf_counter

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app.core.exceptions import GenerationFailedException, ImageGenerationProviderError, InvalidImageGenerationInputError
from app.core.observability import generation_request_context, log_event
from app.pipeline.outfit_pipeline import OutfitPipeline
from app.schemas.generation import GarmentCategory, GarmentInput, GenerateResponse, GenerationInput, ImageAsset
from app.services.image_sizing import inspect_dimensions

router = APIRouter(prefix="/api", tags=["generation"])
_results: dict[str, ImageAsset] = {}
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def _asset(upload: UploadFile, max_size_bytes: int) -> ImageAsset:
    if upload.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=422, detail="업로드한 이미지를 처리할 수 없습니다. JPG, PNG 또는 WEBP 이미지를 사용해주세요.")
    content = await upload.read(max_size_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail=f"{upload.filename or 'file'} is empty")
    if len(content) > max_size_bytes:
        raise HTTPException(status_code=413, detail="이미지 파일이 너무 큽니다. 더 작은 이미지를 사용해주세요.")
    width, height = inspect_dimensions(content)
    return ImageAsset(content=content, content_type=upload.content_type, filename=upload.filename, width=width, height=height)


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    request: Request,
    person: UploadFile = File(...),
    top: UploadFile | None = File(None), bottom: UploadFile | None = File(None), outer: UploadFile | None = File(None),
    shoes: UploadFile | None = File(None), hat: UploadFile | None = File(None), accessory: UploadFile | None = File(None),
    remove_background: bool = Form(True),
) -> GenerateResponse:
    request_id = str(uuid4())
    started_at = perf_counter()
    with generation_request_context(request_id):
        try:
            uploads = {GarmentCategory.TOP: top, GarmentCategory.BOTTOM: bottom, GarmentCategory.OUTER: outer, GarmentCategory.SHOES: shoes, GarmentCategory.HAT: hat, GarmentCategory.ACCESSORY: accessory}
            max_size_bytes = request.app.state.settings.max_upload_size_bytes
            person_asset = await _asset(person, max_size_bytes)
            garments = [GarmentInput(category=category, image=await _asset(upload, max_size_bytes)) for category, upload in uploads.items() if upload is not None]
            if not garments:
                raise HTTPException(status_code=422, detail="At least one fashion item is required")
            log_event(
                "generation.request_received",
                remove_background=remove_background,
                person={"content_type": person_asset.content_type, "bytes": len(person_asset.content), "size": f"{person_asset.width}x{person_asset.height}"},
                garments=[{"category": item.category.value, "content_type": item.image.content_type, "bytes": len(item.image.content), "size": f"{item.image.width}x{item.image.height}"} for item in garments],
            )
            pipeline: OutfitPipeline = request.app.state.pipeline
            output = await pipeline.run(GenerationInput(person=person_asset, garments=garments, remove_background=remove_background))
            result_id = str(uuid4())
            _results[result_id] = output.image
            log_event("generation.request_completed", result_id=result_id, retry_count=output.retry_count, duration_ms=round((perf_counter() - started_at) * 1000))
            return GenerateResponse(result_url=f"/api/results/{result_id}", retry_count=output.retry_count)
        except GenerationFailedException as error:
            log_event("generation.request_failed", status_code=422, error_type=type(error).__name__, duration_ms=round((perf_counter() - started_at) * 1000))
            raise HTTPException(status_code=422, detail="요청한 패션 아이템을 안정적으로 적용하지 못했습니다. 다른 이미지를 사용해 다시 시도해주세요.") from error
        except InvalidImageGenerationInputError as error:
            log_event("generation.request_failed", status_code=422, error_type=type(error).__name__, duration_ms=round((perf_counter() - started_at) * 1000))
            raise HTTPException(status_code=422, detail="업로드한 이미지를 처리할 수 없습니다. JPG 또는 PNG 이미지를 사용해주세요.") from error
        except ImageGenerationProviderError as error:
            log_event("generation.request_failed", status_code=502, error_type=type(error).__name__, duration_ms=round((perf_counter() - started_at) * 1000))
            raise HTTPException(status_code=502, detail="이미지 생성 요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.") from error
        except HTTPException as error:
            log_event("generation.request_failed", status_code=error.status_code, error_type="HTTPException", duration_ms=round((perf_counter() - started_at) * 1000))
            raise


@router.get("/results/{result_id}")
async def get_result(result_id: str) -> Response:
    image = _results.get(result_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return Response(content=image.content, media_type=image.content_type, headers={"Cache-Control": "no-store"})
