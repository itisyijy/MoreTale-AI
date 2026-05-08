from __future__ import annotations

import logging
from typing import Any

from fastapi import BackgroundTasks, HTTPException, status

from app.core.auth import build_error
from app.schemas.story import (
    StoryCreateAcceptedResponse,
    StoryCreateRequest,
    StoryResultResponse,
    StoryStatusResponse,
)
from app.services.generation_pipeline import (
    build_pipeline_request_from_story_request,
    run_story_generation_pipeline,
)
from app.services.job_store import JobStore
from app.services.request_context import log_event
from app.services.output_paths import (
    get_run_dir,
    make_story_id,
    to_static_outputs_url,
)
from app.services.story_result_builder import build_story_result_payload

job_store = JobStore()


def recover_interrupted_jobs() -> None:
    from app.core.config import get_settings

    outputs_dir = get_settings().outputs_dir
    if not outputs_dir.is_dir():
        return

    recovered = 0
    for meta_path in outputs_dir.glob("*/meta.json"):
        try:
            job = job_store.load_job(meta_path.parent.name)
            if job is not None and job.get("status") == "running":
                story_id = str(job.get("id", meta_path.parent.name))
                job_store.mark_failed(
                    story_id=story_id,
                    error={
                        "code": "SERVER_RESTARTED",
                        "message": "job was interrupted by a server restart",
                        "detail": None,
                    },
                )
                recovered += 1
        except Exception:
            pass

    if recovered:
        logging.warning("startup: recovered %d interrupted job(s) → failed", recovered)


def _extract_generation_flags(request_payload: dict[str, Any]) -> tuple[bool, bool, bool, bool]:
    generation = request_payload.get("generation")
    if not isinstance(generation, dict):
        return False, False, False, False

    include_quiz = bool(generation.get("enable_quiz", False))
    include_tts = bool(generation.get("enable_tts", False))
    include_illustration = bool(generation.get("enable_illustration", False))
    include_cover_illustration = include_illustration and bool(
        generation.get("enable_cover_illustration", True)
    )
    return include_quiz, include_tts, include_illustration, include_cover_illustration


def _extract_service_errors(job_payload: dict[str, Any]) -> dict[str, str | None]:
    result = job_payload.get("result")
    if not isinstance(result, dict):
        return {"quiz": None, "tts": None, "illustrations": None}

    assets = result.get("assets")
    if not isinstance(assets, dict):
        return {"quiz": None, "tts": None, "illustrations": None}

    quiz = result.get("quiz")
    tts = assets.get("tts")
    illustrations = assets.get("illustrations")
    quiz_error = quiz.get("service_error") if isinstance(quiz, dict) else None
    tts_error = tts.get("service_error") if isinstance(tts, dict) else None
    illustration_error = (
        illustrations.get("service_error") if isinstance(illustrations, dict) else None
    )
    return {
        "quiz": str(quiz_error) if quiz_error else None,
        "tts": str(tts_error) if tts_error else None,
        "illustrations": str(illustration_error) if illustration_error else None,
    }


def enqueue_story_generation(
    request: StoryCreateRequest,
    background_tasks: BackgroundTasks,
    request_id: str | None = None,
) -> StoryCreateAcceptedResponse:
    story_id = make_story_id(child_name=request.child_name, theme=request.theme)
    request_payload = request.model_dump(mode="json")
    job_store.initialize_job(story_id=story_id, request_payload=request_payload)

    background_tasks.add_task(
        run_story_generation_job_background,
        story_id,
        request_payload,
        request_id,
    )

    log_event(
        event="story.job.queued",
        request_id=request_id,
        story_id=story_id,
        status="queued",
    )

    return StoryCreateAcceptedResponse(
        id=story_id,
        status="queued",
        status_url=f"/api/stories/{story_id}",
        result_url=f"/api/stories/{story_id}/result",
    )


async def run_story_generation_job_background(
    story_id: str,
    request_payload: dict[str, Any],
    request_id: str | None = None,
) -> None:
    run_story_generation_job(
        story_id=story_id,
        request_payload=request_payload,
        request_id=request_id,
    )


def cancel_story_job(story_id: str) -> StoryStatusResponse:
    job = job_store.load_job(story_id=story_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error(
                code="STORY_NOT_FOUND",
                message="story not found",
                detail={"id": story_id},
            ),
        )

    job_status = str(job.get("status", ""))
    if job_status in {"completed", "failed", "canceled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_error(
                code="STORY_CANCEL_NOT_ALLOWED",
                message=f"cannot cancel a job with status '{job_status}'",
                detail={"id": story_id, "status": job_status},
            ),
        )

    updated = job_store.mark_canceled(story_id=story_id)
    log_event(
        event="story.job.canceled",
        story_id=story_id,
        status="canceled",
    )
    return StoryStatusResponse.model_validate(updated)


def load_story_status(story_id: str) -> StoryStatusResponse:
    job = job_store.load_job(story_id=story_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error(
                code="STORY_NOT_FOUND",
                message="story not found",
                detail={"id": story_id},
            ),
        )
    return StoryStatusResponse.model_validate(job)


def load_story_result(story_id: str) -> StoryResultResponse:
    job = job_store.load_job(story_id=story_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error(
                code="STORY_NOT_FOUND",
                message="story not found",
                detail={"id": story_id},
            ),
        )

    job_status = str(job.get("status", ""))
    if job_status not in {"completed", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_error(
                code="STORY_NOT_READY",
                message="story result is not ready",
                detail={"id": story_id, "status": job_status},
            ),
        )

    request_payload = job.get("request")
    (
        _include_quiz,
        include_tts,
        include_illustration,
        include_cover_illustration,
    ) = _extract_generation_flags(
        request_payload if isinstance(request_payload, dict) else {}
    )
    service_errors = _extract_service_errors(job)
    generation = request_payload.get("generation") if isinstance(request_payload, dict) else {}
    illustration_aspect_ratio = (
        str(generation.get("illustration_aspect_ratio", "1:1"))
        if isinstance(generation, dict)
        else "1:1"
    )
    cover_aspect_ratio = (
        str(generation.get("illustration_cover_aspect_ratio", "5:4"))
        if isinstance(generation, dict)
        else "5:4"
    )

    try:
        payload = build_story_result_payload(
            story_id=story_id,
            include_tts=include_tts,
            include_illustration=include_illustration,
            include_cover_illustration=include_cover_illustration,
            illustration_aspect_ratio=illustration_aspect_ratio,
            cover_aspect_ratio=cover_aspect_ratio,
            job_status=job_status,
            service_errors=service_errors,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error(
                code="STORY_RESULT_NOT_FOUND",
                message="story result not found",
                detail={"id": story_id},
            ),
        ) from None
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=build_error(
                code="STORY_RESULT_INVALID",
                message="story result is invalid",
                detail={"id": story_id, "reason": str(error)},
            ),
        ) from None

    return StoryResultResponse.model_validate(payload)


def run_story_generation_job(
    story_id: str,
    request_payload: dict[str, Any],
    request_id: str | None = None,
) -> None:
    (
        include_quiz,
        include_tts,
        include_illustration,
        include_cover_illustration,
    ) = _extract_generation_flags(request_payload)
    service_errors: dict[str, str | None] = {"quiz": None, "tts": None, "illustrations": None}
    story_json_path = None
    quiz_json_path = None
    quiz_result = None
    tts_result: dict[str, Any] | None = None
    illustration_result: dict[str, Any] | None = None
    illustration_aspect_ratio = "1:1"
    cover_aspect_ratio = "5:4"

    current_job = job_store.load_job(story_id)
    if current_job and current_job.get("status") == "canceled":
        log_event(
            event="story.job.skipped",
            request_id=request_id,
            story_id=story_id,
            reason="canceled before execution",
        )
        return

    log_event(
        event="story.job.start",
        request_id=request_id,
        story_id=story_id,
    )

    try:
        request = StoryCreateRequest.model_validate(request_payload)
        illustration_aspect_ratio = request.generation.illustration_aspect_ratio
        cover_aspect_ratio = request.generation.illustration_cover_aspect_ratio
        job_store.mark_running(story_id)
        pipeline_result = run_story_generation_pipeline(
            request=build_pipeline_request_from_story_request(request),
            output_dir_factory=lambda _story, _story_model: get_run_dir(story_id),
            strict_assets=False,
        )
        story_json_path = pipeline_result.story_json_path
        quiz_json_path = pipeline_result.quiz_json_path
        quiz_result = pipeline_result.quiz_result
        tts_result = pipeline_result.tts_result
        illustration_result = pipeline_result.illustration_result
        service_errors = pipeline_result.service_errors

        result_payload = build_story_result_payload(
            story_id=story_id,
            include_tts=include_tts,
            include_illustration=include_illustration,
            include_cover_illustration=include_cover_illustration,
            illustration_aspect_ratio=illustration_aspect_ratio,
            cover_aspect_ratio=cover_aspect_ratio,
            job_status="completed",
            service_errors=service_errors,
        )
        result_summary = {
            "story_json_url": to_static_outputs_url(story_json_path),
            "quiz_json_url": to_static_outputs_url(quiz_json_path) if quiz_json_path else None,
            "quiz": {
                "enabled": request.generation.enable_quiz,
                "service_error": service_errors["quiz"],
            },
            "page_count": result_payload["meta"]["page_count"],
            "assets": result_payload["assets"],
            "raw_service_results": {
                "quiz": quiz_result.model_dump(mode="json") if quiz_result is not None else None,
                "tts": tts_result,
                "illustrations": illustration_result,
            },
        }
        job_store.mark_completed(story_id=story_id, result=result_summary)
        log_event(
            event="story.job.completed",
            request_id=request_id,
            story_id=story_id,
            status="completed",
            has_partial_failures=result_payload["assets"]["has_partial_failures"],
        )
    except Exception as error:
        failed_result: dict[str, Any] | None = None
        if story_json_path is not None:
            try:
                failed_payload = build_story_result_payload(
                    story_id=story_id,
                    include_tts=include_tts,
                    include_illustration=include_illustration,
                    include_cover_illustration=include_cover_illustration,
                    illustration_aspect_ratio=illustration_aspect_ratio,
                    cover_aspect_ratio=cover_aspect_ratio,
                    job_status="failed",
                    service_errors=service_errors,
                )
                failed_result = {
                    "story_json_url": to_static_outputs_url(story_json_path),
                    "quiz_json_url": to_static_outputs_url(quiz_json_path)
                    if quiz_json_path
                    else None,
                    "quiz": {
                        "enabled": include_quiz,
                        "service_error": service_errors["quiz"],
                    },
                    "page_count": failed_payload["meta"]["page_count"],
                    "assets": failed_payload["assets"],
                }
            except Exception:
                failed_result = None

        job_store.mark_failed(
            story_id=story_id,
            error={
                "code": "GENERATION_FAILED",
                "message": "story generation job failed",
                "detail": {"reason": str(error)},
            },
            result=failed_result,
        )
        log_event(
            event="story.job.failed",
            request_id=request_id,
            story_id=story_id,
            status="failed",
            reason=str(error),
            level=logging.ERROR,
        )
