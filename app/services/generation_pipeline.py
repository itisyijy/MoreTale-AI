from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from generators.quiz.quiz_model import Quiz
from generators.story.story_model import Story

from app.schemas.story import StoryCreateRequest

if TYPE_CHECKING:
    from generators.illustration.illustration_pipeline import IllustrationGenerator
    from generators.quiz.quiz_generator import QuizGenerator
    from generators.story.story_generator import StoryGenerator
    from generators.tts.tts_generator import TTSGenerator


@dataclass(frozen=True)
class StoryPipelineRequest:
    child_name: str
    child_age: int | None
    primary_lang: str
    secondary_lang: str
    theme: str = ""
    extra_prompt: str = ""
    include_style_guide: bool = True
    story_model: str = "gemini-2.5-flash"
    enable_quiz: bool = False
    quiz_model: str = "gemini-2.5-flash"
    quiz_question_count: int = 5
    enable_tts: bool = False
    tts_model: str = "gemini-2.5-flash-preview-tts"
    tts_voice: str = "Achernar"
    tts_temperature: float = 1.0
    tts_request_interval_sec: float = 10.0
    enable_illustration: bool = False
    enable_cover_illustration: bool = True
    illustration_model: str = "gemini-2.5-flash-image"
    illustration_aspect_ratio: str = "1:1"
    illustration_cover_aspect_ratio: str = "5:4"
    illustration_request_interval_sec: float = 1.0
    illustration_skip_existing: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "include_style_guide", True)


@dataclass(frozen=True)
class StoryPipelineResult:
    story: Story
    story_model: str
    output_dir: Path
    story_json_path: Path
    quiz_json_path: Path | None
    quiz_result: Quiz | None
    tts_result: dict[str, Any] | None
    illustration_result: dict[str, Any] | None
    service_errors: dict[str, str | None]


def build_pipeline_request_from_story_request(
    request: StoryCreateRequest,
) -> StoryPipelineRequest:
    return StoryPipelineRequest(
        child_name=request.child_name,
        child_age=request.child_age,
        primary_lang=request.primary_lang,
        secondary_lang=request.secondary_lang,
        theme=request.theme,
        extra_prompt=request.extra_prompt,
        include_style_guide=True,
        story_model=request.generation.story_model,
        enable_quiz=request.generation.enable_quiz,
        quiz_model=request.generation.quiz_model,
        quiz_question_count=request.generation.quiz_question_count,
        enable_tts=request.generation.enable_tts,
        tts_model=request.generation.tts_model,
        tts_voice=request.generation.tts_voice,
        tts_temperature=request.generation.tts_temperature,
        tts_request_interval_sec=request.generation.tts_request_interval_sec,
        enable_illustration=request.generation.enable_illustration,
        enable_cover_illustration=request.generation.enable_cover_illustration,
        illustration_model=request.generation.illustration_model,
        illustration_aspect_ratio=request.generation.illustration_aspect_ratio,
        illustration_cover_aspect_ratio=request.generation.illustration_cover_aspect_ratio,
        illustration_request_interval_sec=request.generation.illustration_request_interval_sec,
        illustration_skip_existing=request.generation.illustration_skip_existing,
    )


def generate_story(request: StoryPipelineRequest) -> tuple[Story, str]:
    from generators.story.story_generator import StoryGenerator

    generator = StoryGenerator(
        model_name=request.story_model,
        include_style_guide=request.include_style_guide,
    )
    story = generator.generate_story(
        child_name=request.child_name,
        child_age=request.child_age,
        primary_lang=request.primary_lang,
        secondary_lang=request.secondary_lang,
        theme=request.theme,
        extra_prompt=request.extra_prompt,
    )
    return story, generator.model_name


def generate_quiz(
    request: StoryPipelineRequest,
    story_id: str,
    story: Story,
) -> tuple[Quiz, str]:
    from generators.quiz.quiz_generator import QuizGenerator

    generator = QuizGenerator(model_name=request.quiz_model)
    quiz = generator.generate_quiz(
        story_id=story_id,
        story=story,
        question_count=request.quiz_question_count,
    )
    return quiz, generator.model_name


def generate_tts(
    request: StoryPipelineRequest,
    story: Story,
    output_dir: str | Path,
) -> dict[str, Any]:
    from generators.tts.tts_generator import TTSGenerator

    api_key = (os.getenv("GEMINI_TTS_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_TTS_API_KEY environment variable not set.")

    generator = TTSGenerator(
        api_key=api_key,
        model_name=request.tts_model,
        voice_name=request.tts_voice,
        temperature=request.tts_temperature,
        request_interval_sec=request.tts_request_interval_sec,
    )
    return generator.generate_book_audio(
        story=story,
        output_dir=str(output_dir),
        primary_language=request.primary_lang,
        secondary_language=request.secondary_lang,
        skip_existing=True,
    )


def generate_illustrations(
    request: StoryPipelineRequest,
    story: Story,
    output_dir: str | Path,
) -> dict[str, Any]:
    from generators.illustration.illustration_pipeline import IllustrationGenerator

    api_key = (os.getenv("NANO_BANANA_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("NANO_BANANA_KEY environment variable not set.")

    generator = IllustrationGenerator(
        api_key=api_key,
        model_name=request.illustration_model,
        aspect_ratio=request.illustration_aspect_ratio,
        cover_aspect_ratio=request.illustration_cover_aspect_ratio,
        request_interval_sec=request.illustration_request_interval_sec,
    )
    return generator.generate_from_story(
        story=story,
        output_dir=str(output_dir),
        skip_existing=request.illustration_skip_existing,
        generate_cover=request.enable_cover_illustration,
    )


def write_story_json_to_output_dir(
    output_dir: str | Path,
    story: Story,
    story_model: str,
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    story_json_path = output_path / f"story_{story_model}.json"
    with story_json_path.open("w", encoding="utf-8") as file:
        file.write(story.model_dump_json(indent=4))
    return story_json_path


def write_quiz_json_to_output_dir(
    output_dir: str | Path,
    quiz: Quiz,
    quiz_model: str,
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    quiz_json_path = output_path / f"quiz_{quiz_model}.json"
    with quiz_json_path.open("w", encoding="utf-8") as file:
        file.write(quiz.model_dump_json(indent=4))
    return quiz_json_path


def _raise_on_tts_failures(tts_result: dict[str, Any]) -> None:
    if int(tts_result.get("failed", 0)) <= 0:
        return
    failures = tts_result.get("failures")
    details = "\n".join(failures) if isinstance(failures, list) else ""
    if details:
        raise RuntimeError(f"TTS generation failed.\n{details}")
    raise RuntimeError("TTS generation failed.")


def _raise_on_illustration_failures(illustration_result: dict[str, Any]) -> None:
    if int(illustration_result.get("failed", 0)) <= 0:
        return
    manifest_path = illustration_result.get("manifest_path")
    if manifest_path:
        raise RuntimeError(
            f"Illustration generation failed. See manifest: {manifest_path}"
        )
    raise RuntimeError("Illustration generation failed.")


def run_story_generation_pipeline(
    request: StoryPipelineRequest,
    output_dir_factory: Callable[[Story, str], str | Path],
    *,
    strict_assets: bool,
) -> StoryPipelineResult:
    story, story_model = generate_story(request)
    output_dir = Path(output_dir_factory(story, story_model))
    story_json_path = write_story_json_to_output_dir(output_dir, story, story_model)

    service_errors: dict[str, str | None] = {"quiz": None, "tts": None, "illustrations": None}
    quiz_result: Quiz | None = None
    quiz_json_path: Path | None = None
    tts_result: dict[str, Any] | None = None
    illustration_result: dict[str, Any] | None = None

    if request.enable_quiz:
        try:
            quiz_result, quiz_model = generate_quiz(
                request=request,
                story_id=output_dir.name,
                story=story,
            )
            quiz_json_path = write_quiz_json_to_output_dir(
                output_dir=output_dir,
                quiz=quiz_result,
                quiz_model=quiz_model,
            )
        except Exception as error:
            if strict_assets:
                raise
            service_errors["quiz"] = str(error)

    tts_future: Future[dict[str, Any]] | None = None
    illustration_future: Future[dict[str, Any]] | None = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        if request.enable_tts:
            tts_future = executor.submit(
                generate_tts, request=request, story=story, output_dir=output_dir
            )
        if request.enable_illustration:
            illustration_future = executor.submit(
                generate_illustrations, request=request, story=story, output_dir=output_dir
            )

    if tts_future is not None:
        try:
            tts_result = tts_future.result()
            if strict_assets:
                _raise_on_tts_failures(tts_result)
        except Exception as error:
            if strict_assets:
                raise
            service_errors["tts"] = str(error)

    if illustration_future is not None:
        try:
            illustration_result = illustration_future.result()
            if strict_assets:
                _raise_on_illustration_failures(illustration_result)
        except Exception as error:
            if strict_assets:
                raise
            service_errors["illustrations"] = str(error)

    return StoryPipelineResult(
        story=story,
        story_model=story_model,
        output_dir=output_dir,
        story_json_path=story_json_path,
        quiz_json_path=quiz_json_path,
        quiz_result=quiz_result,
        tts_result=tts_result,
        illustration_result=illustration_result,
        service_errors=service_errors,
    )
