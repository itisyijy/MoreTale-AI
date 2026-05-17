from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from fastapi import BackgroundTasks, HTTPException, status

from app.core.auth import build_error
from app.core.config import get_settings
from app.schemas.internal_ai import (
    InternalJobCreateResponse,
    InternalJobResultResponse,
    InternalJobStatusResponse,
    InternalJobType,
    InternalWebhookPayload,
    QuizInternalJobRequest,
    StoryInternalJobRequest,
    TTSInternalJobRequest,
    VocabInternalJobRequest,
)
from app.schemas.story import StoryError
from app.services.internal_ai_runners import (
    run_quiz_job,
    run_story_job,
    run_tts_job,
    run_vocab_job,
)
from app.services.job_store import JobStore
from app.services.output_paths import slugify
from app.services.request_context import get_request_id, log_event

job_store = JobStore()

_VALID_TYPES: set[str] = {"story", "tts", "quiz", "vocab"}


def make_internal_job_id(job_type: InternalJobType, source: str = "") -> str:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    suffix = slugify(source) or "job"
    base_id = f"{timestamp}_{job_type}_{suffix}"
    outputs_dir = get_settings().outputs_dir
    job_id = base_id
    counter = 1
    while (outputs_dir / job_id).exists():
        job_id = f"{base_id}-{counter:02d}"
        counter += 1
    return job_id


def _status_url(job_id: str) -> str:
    return f"/internal/ai/jobs/{job_id}"


def _result_url(job_type: str, job_id: str) -> str:
    return f"/internal/ai/{job_type}/jobs/{job_id}/result"


def _error_from_payload(error: dict[str, Any] | None) -> StoryError | None:
    if not isinstance(error, dict):
        return None
    return StoryError.model_validate(error)


def _metadata_from_job(job: dict[str, Any]) -> dict[str, Any]:
    request = job.get("request")
    if not isinstance(request, dict):
        request = {}
    job_type = str(request.get("type", ""))
    return {
        "job_id": str(job.get("id", "")),
        "type": job_type,
        "status": str(job.get("status", "")),
        "created_at": str(job.get("created_at", "")),
        "updated_at": str(job.get("updated_at", "")),
        "status_url": _status_url(str(job.get("id", ""))),
        "result_url": _result_url(job_type, str(job.get("id", ""))),
        "callback_url": str(request.get("callback_url", "")),
        "request_id": request.get("request_id"),
        "error": _error_from_payload(job.get("error")),
    }


def _initialize_internal_job(
    *,
    job_type: InternalJobType,
    request_payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> InternalJobCreateResponse:
    callback_url = str(request_payload.get("callback_url", ""))
    request_id = str(request_payload.get("request_id") or get_request_id() or "")
    request_payload = {
        **request_payload,
        "type": job_type,
        "callback_url": callback_url,
        "request_id": request_id or None,
    }
    source = str(
        request_payload.get("story_id")
        or request_payload.get("child_name")
        or request_payload.get("prompt")
        or ""
    )
    job_id = make_internal_job_id(job_type, source=source)
    job_store.initialize_job(story_id=job_id, request_payload=request_payload)
    background_tasks.add_task(run_internal_ai_job_background, job_id)

    log_event(
        event="internal_ai.job.queued",
        job_id=job_id,
        type=job_type,
        status="queued",
        request_id=request_id or None,
    )
    return InternalJobCreateResponse(
        job_id=job_id,
        type=job_type,
        status="queued",
        status_url=_status_url(job_id),
        result_url=_result_url(job_type, job_id),
        callback_url=callback_url,
    )


def enqueue_story_job(
    request: StoryInternalJobRequest,
    background_tasks: BackgroundTasks,
) -> InternalJobCreateResponse:
    return _initialize_internal_job(
        job_type="story",
        request_payload=request.model_dump(mode="json"),
        background_tasks=background_tasks,
    )


def enqueue_tts_job(
    request: TTSInternalJobRequest,
    background_tasks: BackgroundTasks,
) -> InternalJobCreateResponse:
    return _initialize_internal_job(
        job_type="tts",
        request_payload=request.model_dump(mode="json"),
        background_tasks=background_tasks,
    )


def enqueue_quiz_job(
    request: QuizInternalJobRequest,
    background_tasks: BackgroundTasks,
) -> InternalJobCreateResponse:
    return _initialize_internal_job(
        job_type="quiz",
        request_payload=request.model_dump(mode="json"),
        background_tasks=background_tasks,
    )


def enqueue_vocab_job(
    request: VocabInternalJobRequest,
    background_tasks: BackgroundTasks,
) -> InternalJobCreateResponse:
    return _initialize_internal_job(
        job_type="vocab",
        request_payload=request.model_dump(mode="json"),
        background_tasks=background_tasks,
    )


async def run_internal_ai_job_background(job_id: str) -> None:
    job = run_internal_ai_job(job_id)
    await notify_callback(job)


def run_internal_ai_job(job_id: str) -> dict[str, Any]:
    job = job_store.load_job(story_id=job_id)
    if job is None:
        raise RuntimeError(f"internal AI job not found: {job_id}")
    request = job.get("request")
    if not isinstance(request, dict):
        request = {}
    job_type = str(request.get("type", ""))
    if job_type not in _VALID_TYPES:
        raise RuntimeError(f"unsupported internal AI job type: {job_type}")

    job_store.mark_running(story_id=job_id)
    try:
        if job_type == "story":
            data = run_story_job(job_id=job_id, request_payload=request)
        elif job_type == "tts":
            data = run_tts_job(job_id=job_id, request_payload=request)
        elif job_type == "quiz":
            data = run_quiz_job(job_id=job_id, request_payload=request)
        else:
            data = run_vocab_job(request_payload=request)

        completed = job_store.mark_completed(story_id=job_id, result={"data": data})
        log_event(
            event="internal_ai.job.completed",
            job_id=job_id,
            type=job_type,
            status="completed",
        )
        return completed
    except Exception as error:
        failed = job_store.mark_failed(
            story_id=job_id,
            error={
                "code": "AI_JOB_FAILED",
                "message": "internal AI job failed",
                "detail": {"reason": str(error)},
            },
        )
        log_event(
            event="internal_ai.job.failed",
            job_id=job_id,
            type=job_type,
            status="failed",
            reason=str(error),
        )
        return failed


def load_internal_job_status(job_id: str) -> InternalJobStatusResponse:
    job = _load_internal_job(job_id)
    return InternalJobStatusResponse.model_validate(_metadata_from_job(job))


def load_internal_job_result(
    *,
    job_type: InternalJobType,
    job_id: str,
) -> InternalJobResultResponse:
    job = _load_internal_job(job_id)
    request = job.get("request")
    actual_type = str(request.get("type", "")) if isinstance(request, dict) else ""
    if actual_type != job_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error(
                code="AI_JOB_NOT_FOUND",
                message="internal AI job not found for type",
                detail={"job_id": job_id, "type": job_type},
            ),
        )

    job_status = str(job.get("status", ""))
    if job_status not in {"completed", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_error(
                code="AI_JOB_NOT_READY",
                message="internal AI job result is not ready",
                detail={"job_id": job_id, "status": job_status},
            ),
        )

    result = job.get("result")
    data = result.get("data") if isinstance(result, dict) else None
    return InternalJobResultResponse(
        job_id=job_id,
        type=job_type,
        status=job_status,
        data=data,
        error=_error_from_payload(job.get("error")),
    )


def _load_internal_job(job_id: str) -> dict[str, Any]:
    job = job_store.load_job(story_id=job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error(
                code="AI_JOB_NOT_FOUND",
                message="internal AI job not found",
                detail={"job_id": job_id},
            ),
        )
    request = job.get("request")
    if not isinstance(request, dict) or str(request.get("type", "")) not in _VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error(
                code="AI_JOB_NOT_FOUND",
                message="internal AI job not found",
                detail={"job_id": job_id},
            ),
        )
    return job


async def notify_callback(job: dict[str, Any]) -> None:
    request = job.get("request")
    if not isinstance(request, dict):
        return
    callback_url = str(request.get("callback_url", "")).strip()
    job_type = str(request.get("type", "")).strip()
    job_id = str(job.get("id", ""))
    if not callback_url or job_type not in _VALID_TYPES:
        return

    payload = InternalWebhookPayload(
        job_id=job_id,
        type=job_type,  # type: ignore[arg-type]
        status="completed" if job.get("status") == "completed" else "failed",
        result_url=_result_url(job_type, job_id),
        error=_error_from_payload(job.get("error")),
        request_id=request.get("request_id"),
    ).model_dump(mode="json", by_alias=True)

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(callback_url, json=payload)
                response.raise_for_status()
            log_event(
                event="internal_ai.webhook.sent",
                job_id=job_id,
                type=job_type,
                callback_url=callback_url,
            )
            return
        except Exception as error:
            last_error = error
            if attempt < 2:
                await asyncio.sleep(0.2 * (attempt + 1))

    log_event(
        event="internal_ai.webhook.failed",
        job_id=job_id,
        type=job_type,
        callback_url=callback_url,
        reason=str(last_error) if last_error else "",
    )
