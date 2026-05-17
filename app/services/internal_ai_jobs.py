from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
import wave
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
    TTSInput,
    TTSInternalJobRequest,
    VocabInternalJobRequest,
)
from app.schemas.story import StoryError
from app.services.generation_pipeline import run_story_generation_pipeline
from app.services.job_store import JobStore
from app.services.output_paths import get_run_dir, slugify, to_static_outputs_url
from app.services.request_context import get_request_id, log_event

job_store = JobStore()

_VALID_TYPES: set[str] = {"story", "tts", "quiz", "vocab"}

_TTS_LOCALE_TO_CANONICAL: dict[str, str] = {
    "ko-kr": "ko-KR",
    "en-us": "en-US",
    "ja-jp": "ja-JP",
    "zh-cn": "zh-CN",
    "es-es": "es-ES",
    "vi-vn": "vi-VN",
}


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


def run_story_job(job_id: str, request_payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.backend_mapper import (
        map_generate_request_to_pipeline,
        map_story_to_generate_response,
    )

    request = StoryInternalJobRequest.model_validate(request_payload)
    pipeline_request = map_generate_request_to_pipeline(request)
    pipeline_result = run_story_generation_pipeline(
        request=pipeline_request,
        output_dir_factory=lambda _story, _story_model: get_run_dir(job_id),
        strict_assets=False,
    )
    response = map_story_to_generate_response(pipeline_result.story, request)
    return response.model_dump(mode="json", by_alias=True)


def _tts_inputs_from_request(request: TTSInternalJobRequest) -> list[TTSInput]:
    if request.inputs:
        return request.inputs
    return [
        TTSInput(
            id="1",
            text=request.text or "",
            language=request.language or "",
            style=request.style,
        )
    ]


def _normalize_tts_language(language: str) -> str:
    normalized = language.strip()
    return _TTS_LOCALE_TO_CANONICAL.get(normalized.lower(), normalized)


def _build_styled_tts_prompt(
    generator: Any,
    *,
    language: str,
    text: str,
    style: str | None,
) -> str:
    prompt = generator._build_prompt(language_name=language, text=text)
    normalized_style = (style or "").strip()
    if normalized_style:
        return f"{prompt}\nVoice style: {normalized_style}."
    return prompt


def _wav_duration_seconds(file_path: os.PathLike[str] | str) -> int:
    try:
        with wave.open(str(file_path), "rb") as audio:
            frame_count = audio.getnframes()
            frame_rate = audio.getframerate()
    except (EOFError, OSError, wave.Error):
        return 0
    if frame_count <= 0 or frame_rate <= 0:
        return 0
    return max(1, math.ceil(frame_count / frame_rate))


def run_tts_job(job_id: str, request_payload: dict[str, Any]) -> dict[str, Any]:
    from generators.tts.tts_generator import TTSGenerator

    request = TTSInternalJobRequest.model_validate(request_payload)
    api_key = (os.getenv("GEMINI_TTS_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_TTS_API_KEY environment variable not set.")

    generator = TTSGenerator(
        api_key=api_key,
        model_name=request.model,
        voice_name=request.voice,
        temperature=request.temperature,
    )
    output_dir = get_run_dir(job_id) / "tts"
    output_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    for index, item in enumerate(_tts_inputs_from_request(request), start=1):
        language = _normalize_tts_language(item.language)
        prompt = _build_styled_tts_prompt(
            generator,
            language=language,
            text=item.text,
            style=item.style or request.style,
        )
        contents = generator._build_contents(prompt)
        audio_bytes, mime_type = generator._stream_audio_bytes(
            contents=contents,
            config=generator._build_config(),
        )
        file_path = output_dir / f"tts_{index:03d}.wav"
        generator._save_audio_file(str(file_path), audio_bytes, mime_type)
        duration = _wav_duration_seconds(file_path)
        items.append(
            {
                "id": item.id or str(index),
                "language": language,
                "audioUrl": to_static_outputs_url(file_path),
                "duration": duration,
                "message": "TTS generation completed",
            }
        )

    return {
        "items": items,
        "audioUrl": items[0]["audioUrl"] if len(items) == 1 else None,
        "language": items[0]["language"] if len(items) == 1 else None,
        "duration": items[0]["duration"] if len(items) == 1 else None,
        "message": items[0]["message"] if len(items) == 1 else "TTS batch generation completed",
    }


def run_quiz_job(job_id: str, request_payload: dict[str, Any]) -> dict[str, Any]:
    from generators.quiz.quiz_generator import QuizGenerator
    from generators.story.story_model import Story

    request = QuizInternalJobRequest.model_validate(request_payload)
    story_payload = request.story or _load_story_json_from_url(request.story_json_url or "")
    story = Story.model_validate(story_payload)
    generator = QuizGenerator(model_name=request.model)
    quiz = generator.generate_quiz(
        story_id=request.story_id,
        story=story,
        question_count=request.question_count,
    )

    run_dir = get_run_dir(job_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    quiz_path = run_dir / f"quiz_{generator.model_name}.json"
    quiz_path.write_text(quiz.model_dump_json(indent=4), encoding="utf-8")
    return {
        **_camelize(quiz.model_dump(mode="json")),
        "quizJsonUrl": to_static_outputs_url(quiz_path),
    }


def _camelize(value: Any) -> Any:
    if isinstance(value, list):
        return [_camelize(item) for item in value]
    if isinstance(value, dict):
        return {_to_camel_key(str(key)): _camelize(item) for key, item in value.items()}
    return value


def _to_camel_key(value: str) -> str:
    parts = value.split("_")
    if not parts:
        return value
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _load_story_json_from_url(url: str) -> dict[str, Any]:
    if url.startswith("/static/outputs/"):
        relative = url.removeprefix("/static/outputs/").lstrip("/")
        path = get_settings().outputs_dir / relative
        return json.loads(path.read_text(encoding="utf-8"))

    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("storyJsonUrl must return a JSON object")
    return payload


def run_vocab_job(request_payload: dict[str, Any]) -> dict[str, Any]:
    request = VocabInternalJobRequest.model_validate(request_payload)
    entries: list[dict[str, Any]] = []
    for slide in request.slides:
        if slide.vocabulary:
            entries.extend(_entries_from_supplied_vocabulary(slide.order, slide.vocabulary))
        else:
            entries.extend(_entries_from_slide_text(slide.order, slide.text_kr, slide.text_native))

    return {
        "storyId": request.story_id,
        "primaryLanguage": request.primary_language,
        "secondaryLanguage": request.secondary_language,
        "entries": entries,
    }


def _entries_from_supplied_vocabulary(
    order: int,
    vocabulary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, raw in enumerate(vocabulary, start=1):
        primary = str(raw.get("primary_word") or raw.get("primaryWord") or "").strip()
        secondary = str(raw.get("secondary_word") or raw.get("secondaryWord") or "").strip()
        if not primary and not secondary:
            continue
        entries.append(
            {
                "slideOrder": order,
                "entryId": str(raw.get("entry_id") or raw.get("entryId") or f"{order}-{index}"),
                "primaryWord": primary,
                "secondaryWord": secondary,
                "primaryDefinition": str(
                    raw.get("primary_definition") or raw.get("primaryDefinition") or ""
                ),
                "secondaryDefinition": str(
                    raw.get("secondary_definition") or raw.get("secondaryDefinition") or ""
                ),
            }
        )
    return entries


def _entries_from_slide_text(order: int, text_kr: str, text_native: str) -> list[dict[str, Any]]:
    primary_terms = _extract_terms(text_kr)
    secondary_terms = _extract_terms(text_native)
    count = max(len(primary_terms), len(secondary_terms))
    entries: list[dict[str, Any]] = []
    for index in range(min(count, 5)):
        entries.append(
            {
                "slideOrder": order,
                "entryId": f"{order}-{index + 1}",
                "primaryWord": primary_terms[index] if index < len(primary_terms) else "",
                "secondaryWord": secondary_terms[index] if index < len(secondary_terms) else "",
                "primaryDefinition": "",
                "secondaryDefinition": "",
            }
        )
    return entries


def _extract_terms(text: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z가-힣]{2,}", text or ""):
        normalized = token.strip()
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(normalized)
    return terms[:5]


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
