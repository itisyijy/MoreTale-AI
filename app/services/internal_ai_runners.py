from __future__ import annotations

import json
import math
import os
import re
import wave
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.languages import normalize_tts_locale
from app.schemas.internal_ai import (
    QuizInternalJobRequest,
    StoryInternalJobRequest,
    TTSInput,
    TTSInternalJobRequest,
    VocabInternalJobRequest,
)
from app.services.generation_pipeline import run_story_generation_pipeline
from app.services.output_paths import get_run_dir, to_static_outputs_url


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
        language = normalize_tts_locale(item.language)
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
