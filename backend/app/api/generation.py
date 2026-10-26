from uuid import uuid4
from time import perf_counter

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app.core.exceptions import GenerationFailedException, ImageGenerationProviderError, InvalidImageGenerationInputError
from app.core.observability import generation_request_context, log_event
from app.pipeline.outfit_pipeline import OutfitPipeline
from app.schemas.generation import GarmentCategory, GarmentInput, GenerateResponse, GenerationInput, ImageAsset
from app.schemas.garment_preparation import GarmentPreparationResponse
from app.services.garment_preparer import GarmentPreparer
from app.services.image_sizing import inspect_dimensions
from app.services.temporary_image_store import ImageTooLargeToStoreError, StoreResult, TemporaryImageStore

router = APIRouter(prefix="/api", tags=["generation"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
_RESULT = "result"
_CUTOUT = "cutout"
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_STORE_FULL_DETAIL = "결과 이미지가 너무 커서 임시 저장할 수 없습니다. 더 작은 이미지로 다시 시도해주세요."


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)


def _image_store(request: Request) -> TemporaryImageStore:
    return request.app.state.image_store


def _store_payload(store: TemporaryImageStore, saved: StoreResult) -> dict[str, int]:
    stats = store.stats()
    return {"items": stats.items, "bytes": stats.bytes, "max_bytes": stats.max_bytes, "evicted": saved.evicted, "expired": saved.expired}


def _image_payload(image: ImageAsset) -> dict[str, object]:
    return {"content_type": image.content_type, "bytes": len(image.content), "size": f"{image.width}x{image.height}" if image.width and image.height else None}


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


@router.post("/garments/prepare", response_model=GarmentPreparationResponse)
async def prepare_garment(
    request: Request,
    image: UploadFile = File(...),
    requested_category: GarmentCategory = Form(...),
) -> GarmentPreparationResponse:
    request_id = str(uuid4())
    started_at = perf_counter()
    with generation_request_context(request_id):
        try:
            asset = await _asset(image, request.app.state.settings.max_upload_size_bytes)
            log_event(
                "garment.preparation.request_received",
                requested_category=requested_category.value,
                image={"content_type": asset.content_type, "bytes": len(asset.content), "size": f"{asset.width}x{asset.height}"},
            )
            preparer: GarmentPreparer = request.app.state.garment_preparer
            preparation = await preparer.prepare(asset, requested_category)
            store = _image_store(request)
            store_started_at = perf_counter()
            saved = store.put(_CUTOUT, preparation.cutout)
            log_event(
                "garment.preparation.request_completed",
                duration_ms=_elapsed_ms(started_at), store_ms=_elapsed_ms(store_started_at),
                output=_image_payload(preparation.cutout), store=_store_payload(store, saved),
            )
            return GarmentPreparationResponse(
                detected_category=preparation.detected_category,
                confidence=preparation.confidence,
                quality=preparation.quality,
                issues=preparation.issues,
                cutout_url=f"/api/cutouts/{saved.image_id}",
            )
        except InvalidImageGenerationInputError as error:
            log_event("garment.preparation.request_failed", status_code=422, error_type=type(error).__name__, duration_ms=_elapsed_ms(started_at))
            raise HTTPException(status_code=422, detail="의류 이미지를 분석할 수 없습니다. 다른 사진을 사용해주세요.") from error
        except ImageGenerationProviderError as error:
            log_event("garment.preparation.request_failed", status_code=502, error_type=type(error).__name__, duration_ms=_elapsed_ms(started_at))
            raise HTTPException(status_code=502, detail="의류 자동 컷아웃을 만들지 못했습니다. 잠시 후 다시 시도해주세요.") from error
        except ImageTooLargeToStoreError as error:
            log_event("garment.preparation.request_failed", status_code=507, error_type=type(error).__name__, duration_ms=_elapsed_ms(started_at))
            raise HTTPException(status_code=507, detail=_STORE_FULL_DETAIL) from error
        except HTTPException as error:
            log_event("garment.preparation.request_failed", status_code=error.status_code, error_type="HTTPException", duration_ms=_elapsed_ms(started_at))
            raise


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
            upload_ms = _elapsed_ms(started_at)
            log_event(
                "generation.request_received",
                remove_background=remove_background,
                person={"content_type": person_asset.content_type, "bytes": len(person_asset.content), "size": f"{person_asset.width}x{person_asset.height}"},
                garments=[{"category": item.category.value, "content_type": item.image.content_type, "bytes": len(item.image.content), "size": f"{item.image.width}x{item.image.height}"} for item in garments],
            )
            pipeline: OutfitPipeline = request.app.state.pipeline
            output = await pipeline.run(GenerationInput(person=person_asset, garments=garments, remove_background=remove_background))
            store = _image_store(request)
            store_started_at = perf_counter()
            saved = store.put(_RESULT, output.image)
            log_event(
                "generation.request_completed",
                result_id=saved.image_id, retry_count=output.retry_count, duration_ms=_elapsed_ms(started_at),
                stage_ms={"upload": upload_ms, **output.stage_ms, "store": _elapsed_ms(store_started_at)},
                output=_image_payload(output.image), store=_store_payload(store, saved),
            )
            return GenerateResponse(result_url=f"/api/results/{saved.image_id}", retry_count=output.retry_count)
        except GenerationFailedException as error:
            log_event("generation.request_failed", status_code=422, error_type=type(error).__name__, duration_ms=_elapsed_ms(started_at))
            raise HTTPException(status_code=422, detail="요청한 패션 아이템을 안정적으로 적용하지 못했습니다. 다른 이미지를 사용해 다시 시도해주세요.") from error
        except InvalidImageGenerationInputError as error:
            log_event("generation.request_failed", status_code=422, error_type=type(error).__name__, duration_ms=_elapsed_ms(started_at))
            raise HTTPException(status_code=422, detail="업로드한 이미지를 처리할 수 없습니다. JPG 또는 PNG 이미지를 사용해주세요.") from error
        except ImageGenerationProviderError as error:
            log_event("generation.request_failed", status_code=502, error_type=type(error).__name__, duration_ms=_elapsed_ms(started_at))
            raise HTTPException(status_code=502, detail="이미지 생성 요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.") from error
        except ImageTooLargeToStoreError as error:
            log_event("generation.request_failed", status_code=507, error_type=type(error).__name__, duration_ms=_elapsed_ms(started_at))
            raise HTTPException(status_code=507, detail=_STORE_FULL_DETAIL) from error
        except HTTPException as error:
            log_event("generation.request_failed", status_code=error.status_code, error_type="HTTPException", duration_ms=_elapsed_ms(started_at))
            raise


@router.get("/results/{result_id}")
async def get_result(request: Request, result_id: str) -> Response:
    image = _image_store(request).get(_RESULT, result_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Result not found or expired")
    return Response(content=image.content, media_type=image.content_type, headers={"Cache-Control": "no-store"})


@router.get("/cutouts/{cutout_id}")
async def get_cutout(request: Request, cutout_id: str) -> Response:
    image = _image_store(request).get(_CUTOUT, cutout_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Cutout not found or expired")
    return Response(content=image.content, media_type=image.content_type, headers={"Cache-Control": "no-store"})
