from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.core.auth import require_api_key
from app.schemas.internal_ai import (
    InternalJobCreateResponse,
    InternalJobResultResponse,
    InternalJobStatusResponse,
    InternalJobType,
    QuizInternalJobRequest,
    StoryInternalJobRequest,
    TTSInternalJobRequest,
    VocabInternalJobRequest,
)
from app.schemas.story import ErrorResponse
from app.services.internal_ai_jobs import (
    enqueue_quiz_job,
    enqueue_story_job,
    enqueue_tts_job,
    enqueue_vocab_job,
    load_internal_job_result,
    load_internal_job_status,
)

router = APIRouter(
    prefix="/internal/ai",
    tags=["internal-ai"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/story/jobs",
    response_model=InternalJobCreateResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_story_job(
    request: StoryInternalJobRequest,
    background_tasks: BackgroundTasks,
) -> InternalJobCreateResponse:
    return enqueue_story_job(request=request, background_tasks=background_tasks)


@router.post(
    "/tts/jobs",
    response_model=InternalJobCreateResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_tts_job(
    request: TTSInternalJobRequest,
    background_tasks: BackgroundTasks,
) -> InternalJobCreateResponse:
    return enqueue_tts_job(request=request, background_tasks=background_tasks)


@router.post(
    "/quiz/jobs",
    response_model=InternalJobCreateResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_quiz_job(
    request: QuizInternalJobRequest,
    background_tasks: BackgroundTasks,
) -> InternalJobCreateResponse:
    return enqueue_quiz_job(request=request, background_tasks=background_tasks)


@router.post(
    "/vocab/jobs",
    response_model=InternalJobCreateResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_vocab_job(
    request: VocabInternalJobRequest,
    background_tasks: BackgroundTasks,
) -> InternalJobCreateResponse:
    return enqueue_vocab_job(request=request, background_tasks=background_tasks)


@router.get(
    "/jobs/{job_id}",
    response_model=InternalJobStatusResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_internal_job(job_id: str) -> InternalJobStatusResponse:
    return load_internal_job_status(job_id=job_id)


@router.get(
    "/{job_type}/jobs/{job_id}/result",
    response_model=InternalJobResultResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def get_internal_job_result(
    job_type: InternalJobType,
    job_id: str,
) -> InternalJobResultResponse:
    return load_internal_job_result(job_type=job_type, job_id=job_id)
