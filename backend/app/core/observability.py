"""Human-readable, dependency-free logging for generation requests.

The log payload deliberately contains image metadata only.  It never writes image
bytes, filenames, prompts, or credentials to stdout.
"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator

_request_id: ContextVar[str | None] = ContextVar("generation_request_id", default=None)
logger = logging.getLogger("try_on_me.observability")


def configure_observability(level: str) -> None:
    """Let Uvicorn own the output handler while this logger controls its level."""
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))


@contextmanager
def generation_request_context(request_id: str) -> Iterator[None]:
    token = _request_id.set(request_id)
    try:
        yield
    finally:
        _request_id.reset(token)


def log_event(event: str, **attributes: Any) -> None:
    """Emit a compact terminal event and retain its fields on the log record."""
    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
    }
    if request_id := _request_id.get():
        payload["request_id"] = request_id
    payload.update({key: value for key, value in attributes.items() if value is not None})
    logger.info("%s", _format_event(payload), extra={"event_data": payload})


def _format_bytes(byte_count: int) -> str:
    if byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.0f} KB"
    return f"{byte_count / (1024 * 1024):.1f} MB"


def _format_images(images: list[dict[str, Any]]) -> str:
    return " · ".join(
        f"{image['role']} ({image['content_type']}, {_format_bytes(image['bytes'])})" for image in images
    )


def _format_usage(usage: dict[str, Any] | None) -> str | None:
    if not usage:
        return None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")
    input_detail = " · ".join(
        part for part in [
            f"이미지 {usage['input_image_tokens']}" if usage.get("input_image_tokens") is not None else None,
            f"텍스트 {usage['input_text_tokens']}" if usage.get("input_text_tokens") is not None else None,
        ] if part
    )
    output_detail = f"이미지 {usage['output_image_tokens']}" if usage.get("output_image_tokens") is not None else None
    parts = [
        f"입력 {input_tokens}" + (f" ({input_detail})" if input_detail else "") if input_tokens is not None else None,
        f"출력 {output_tokens}" + (f" ({output_detail})" if output_detail else "") if output_tokens is not None else None,
        f"합계 {total_tokens}" if total_tokens is not None else None,
    ]
    return " | ".join(part for part in parts if part)


def _format_event(payload: dict[str, Any]) -> str:
    event = payload["event"]
    request_id = payload.get("request_id", "-")[:8]
    prefix = f"[TRY-ON {request_id}]"
    duration = f"{payload['duration_ms'] / 1000:.1f}초" if payload.get("duration_ms", 0) >= 1000 else f"{payload.get('duration_ms', 0)}ms"

    if event == "generation.request_received":
        person = payload["person"]
        garments = " · ".join(
            f"{item['category']} ({item['content_type']}, {_format_bytes(item['bytes'])})" for item in payload["garments"]
        )
        return f"{prefix} 생성 요청 접수\n  입력  사람 ({person['content_type']}, {person['size']}, {_format_bytes(person['bytes'])}) | 의류 {garments}\n  옵션  배경 제거 {'사용' if payload['remove_background'] else '사용 안 함'}"
    if event == "llm.call.started":
        source_size = f" | 원본 {payload['source_size']}" if payload.get("source_size") else ""
        return f"{prefix} OpenAI 이미지 생성 시작\n  모델  {payload['model']} | API 생성 {payload['size']}{source_size}\n  품질  {payload['quality']}\n  참조  {_format_images(payload['input_images'])}"
    if event == "llm.call.completed":
        output_size = f" · {payload['output_size']}" if payload.get("output_size") else ""
        lines = [f"{prefix} OpenAI 이미지 생성 완료 · {duration}", f"  모델  {payload['model']} | 결과 {payload['output_content_type']}{output_size} · {_format_bytes(payload['output_bytes'])}"]
        if usage := _format_usage(payload.get("usage")):
            lines.append(f"  토큰  {usage}")
        if openai_request_id := payload.get("openai_request_id"):
            lines.append(f"  OpenAI 요청 ID  {openai_request_id}")
        return "\n".join(lines)
    if event == "llm.call.failed":
        return f"{prefix} OpenAI 이미지 생성 실패 · {duration}\n  모델  {payload['model']} | 원인 {payload['error_type']}"
    if event == "pipeline.started":
        garments = ", ".join(payload["garment_categories"])
        return f"{prefix} 파이프라인 시작\n  의류 카테고리  {garments} | 배경 제거 {'사용' if payload['remove_background'] else '사용 안 함'}"
    if event == "pipeline.preprocessing.completed":
        return f"{prefix} 전처리 완료 · {duration}"
    if event == "pipeline.generation.completed":
        return f"{prefix} 생성 단계 완료 · {duration} (시도 {payload['attempt']})"
    if event == "pipeline.safety.completed":
        return f"{prefix} 안전성 검사 {'통과' if payload['safe'] else '재시도 필요'} · {duration} (시도 {payload['attempt']})"
    if event == "pipeline.quality.completed":
        suffix = "" if payload["valid"] else f" | 이슈: {', '.join(payload['issues'])}"
        return f"{prefix} 품질 검사 {'통과' if payload['valid'] else '재시도 필요'} · {duration} (시도 {payload['attempt']}){suffix}"
    if event == "pipeline.completed":
        return f"{prefix} 파이프라인 완료 · {duration} | 재시도 {payload['retry_count']}회"
    if event == "pipeline.failed":
        return f"{prefix} 파이프라인 실패 · {duration} | 총 {payload['attempts']}회 시도"
    if event == "generation.request_completed":
        return f"{prefix} 요청 완료 · {duration} | 재시도 {payload['retry_count']}회 | 결과 ID {payload['result_id'][:8]}"
    if event == "generation.request_failed":
        return f"{prefix} 요청 실패 · {duration} | HTTP {payload['status_code']} | {payload['error_type']}"
    return f"{prefix} {event}"
