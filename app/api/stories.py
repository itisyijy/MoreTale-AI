from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.core.auth import build_error, require_api_key
from app.core.config import get_settings
from app.schemas.story import (
    ErrorResponse,
    StoryCreateAcceptedResponse,
    StoryCreateRequest,
    StoryGenerateRequest,
    StoryResultResponse,
    StoryStatusResponse,
)
from app.services.rate_limiter import post_stories_rate_limiter
from app.services.request_context import get_request_id
from app.services.story_orchestrator import (
    cancel_story_job,
    enqueue_story_generation,
    enqueue_story_generation_backend,
    load_story_result,
    load_story_status,
)

router = APIRouter(
    prefix="/api/stories",
    tags=["stories"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "/",
    response_model=StoryCreateAcceptedResponse,
    responses={
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_story(
    http_request: Request,
    request: StoryCreateRequest,
    background_tasks: BackgroundTasks,
) -> StoryCreateAcceptedResponse:
    api_key = (http_request.headers.get("X-API-Key") or "").strip()
    limit_per_min = get_settings().rate_limit_post_stories_per_min
    if not post_stories_rate_limiter.is_allowed(
        key=api_key,
        limit_per_min=limit_per_min,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=build_error(
                code="RATE_LIMIT_EXCEEDED",
                message="rate limit exceeded",
                detail={"limit_per_min": limit_per_min},
            ),
        )

    return enqueue_story_generation(
        request=request,
        background_tasks=background_tasks,
        request_id=get_request_id(),
    )


@router.get(
    "/{story_id}",
    response_model=StoryStatusResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_story(story_id: str) -> StoryStatusResponse:
    return load_story_status(story_id=story_id)


@router.get(
    "/{story_id}/result",
    response_model=StoryResultResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_story_result(story_id: str) -> StoryResultResponse:
    return load_story_result(story_id=story_id)


@router.post(
    "/generate",
    response_model=StoryCreateAcceptedResponse,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_story_backend(
    http_request: Request,
    request: StoryGenerateRequest,
    background_tasks: BackgroundTasks,
) -> StoryCreateAcceptedResponse:
    api_key = (http_request.headers.get("X-API-Key") or "").strip()
    limit_per_min = get_settings().rate_limit_post_stories_per_min
    if not post_stories_rate_limiter.is_allowed(
        key=api_key,
        limit_per_min=limit_per_min,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=build_error(
                code="RATE_LIMIT_EXCEEDED",
                message="rate limit exceeded",
                detail={"limit_per_min": limit_per_min},
            ),
        )

    return enqueue_story_generation_backend(
        request=request,
        background_tasks=background_tasks,
        request_id=get_request_id(),
    )


@router.delete(
    "/{story_id}",
    response_model=StoryStatusResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def cancel_story(story_id: str) -> StoryStatusResponse:
    return cancel_story_job(story_id=story_id)
