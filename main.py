from __future__ import annotations

import argparse
import datetime
import sys
import traceback
from pathlib import Path

from app.services.generation_pipeline import (
    StoryPipelineRequest,
    run_story_generation_pipeline,
)
from app.services.output_paths import slugify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a bilingual fairy tale.")
    parser.add_argument("--child_name", required=True, help="Name of the child")
    parser.add_argument(
        "--child_age",
        type=int,
        default=None,
        help="Child age (optional, recommended for age-appropriate complexity)",
    )
    parser.add_argument("--primary_lang", required=True, help="Primary language (Child's context)")
    parser.add_argument("--secondary_lang", required=True, help="Secondary language (Parent's heritage)")
    parser.add_argument(
        "--theme",
        default="",
        help="Theme of the story (optional). If omitted, the model will auto-generate a theme.",
    )
    parser.add_argument("--extra_prompt", default="", help="Additional request or details")
    parser.add_argument("--model_name", default="gemini-2.5-flash", help="Gemini model name to use")
    parser.add_argument(
        "--enable_quiz",
        action="store_true",
        help="Generate a story-comprehension quiz JSON with answer key.",
    )
    parser.add_argument(
        "--quiz_model",
        default="gemini-2.5-flash",
        help="Gemini model name to use when --enable_quiz is set.",
    )
    parser.add_argument(
        "--quiz_question_count",
        type=int,
        default=5,
        help="Number of quiz questions to generate when --enable_quiz is set.",
    )
    parser.add_argument(
        "--include_style_guide",
        action="store_true",
        help="Deprecated no-op. prompts/style_guide.txt is always included in the system instruction.",
    )
    parser.add_argument(
        "--enable_tts",
        action="store_true",
        help="Generate page-level audiobook WAV files (primary/secondary language split).",
    )
    parser.add_argument(
        "--tts_model",
        default="gemini-2.5-flash-preview-tts",
        help="Gemini TTS model name to use when --enable_tts is set.",
    )
    parser.add_argument(
        "--tts_voice",
        default="Achernar",
        help="Voice name for Gemini TTS when --enable_tts is set.",
    )
    parser.add_argument(
        "--tts_temperature",
        type=float,
        default=1.0,
        help="TTS temperature when --enable_tts is set.",
    )
    parser.add_argument(
        "--tts_request_interval_sec",
        type=float,
        default=10.0,
        help="Seconds between TTS requests to respect RPM limits.",
    )
    parser.add_argument(
        "--enable_illustration",
        action="store_true",
        help="Generate a cover plus page-level illustrations from the story JSON.",
    )
    parser.add_argument(
        "--illustration_model",
        default="gemini-2.5-flash-image",
        help="Gemini image model name to use when --enable_illustration is set.",
    )
    parser.add_argument(
        "--illustration_aspect_ratio",
        default="1:1",
        help="Interior illustration aspect ratio when --enable_illustration is set (e.g. 1:1, 4:3).",
    )
    parser.add_argument(
        "--illustration_cover_aspect_ratio",
        default="5:4",
        help="Cover illustration aspect ratio when --enable_illustration is set (e.g. 5:4).",
    )
    parser.add_argument(
        "--illustration_request_interval_sec",
        type=float,
        default=1.0,
        help="Seconds between image requests when --enable_illustration is set.",
    )
    parser.add_argument(
        "--illustration_skip_existing",
        action="store_true",
        help="Skip pages if page_XX.* already exists when --enable_illustration is set.",
    )
    parser.add_argument(
        "--illustration_skip_cover",
        action="store_true",
        help="Skip cover generation and only create interior illustrations.",
    )
    return parser


def build_pipeline_request(args: argparse.Namespace) -> StoryPipelineRequest:
    return StoryPipelineRequest(
        child_name=args.child_name,
        child_age=args.child_age,
        primary_lang=args.primary_lang,
        secondary_lang=args.secondary_lang,
        theme=args.theme,
        extra_prompt=args.extra_prompt,
        include_style_guide=True,
        story_model=args.model_name,
        enable_quiz=args.enable_quiz,
        quiz_model=args.quiz_model,
        quiz_question_count=args.quiz_question_count,
        enable_tts=args.enable_tts,
        tts_model=args.tts_model,
        tts_voice=args.tts_voice,
        tts_temperature=args.tts_temperature,
        tts_request_interval_sec=args.tts_request_interval_sec,
        enable_illustration=args.enable_illustration,
        enable_cover_illustration=not args.illustration_skip_cover,
        illustration_model=args.illustration_model,
        illustration_aspect_ratio=args.illustration_aspect_ratio,
        illustration_cover_aspect_ratio=args.illustration_cover_aspect_ratio,
        illustration_request_interval_sec=args.illustration_request_interval_sec,
        illustration_skip_existing=args.illustration_skip_existing,
    )


def build_output_dir(timestamp: str, story, _story_model: str) -> Path:
    safe_title = slugify(getattr(story, "title_primary", ""))
    if not safe_title:
        safe_title = slugify(getattr(story, "title_secondary", ""))
    if not safe_title:
        safe_title = "story"
    return Path("outputs") / f"{timestamp}_story_{safe_title}"


def main() -> None:
    args = build_parser().parse_args()
    pipeline_request = build_pipeline_request(args)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print("Generating bilingual fairy tale...")

    try:
        result = run_story_generation_pipeline(
            request=pipeline_request,
            output_dir_factory=lambda story, story_model: build_output_dir(
                timestamp, story, story_model
            ),
            strict_assets=True,
        )

        print(f"Generated story: {result.story.title_primary}")
        print(f"Story saved to: {result.story_json_path}")
        if pipeline_request.enable_quiz:
            print(f"Quiz saved to: {result.quiz_json_path}")

        if pipeline_request.enable_tts and result.tts_result is not None:
            print(
                "TTS summary: "
                f"total={result.tts_result['total_tasks']} "
                f"generated={result.tts_result['generated']} "
                f"skipped={result.tts_result['skipped']} "
                f"failed={result.tts_result['failed']}"
            )

        if pipeline_request.enable_illustration and result.illustration_result is not None:
            print(
                "Illustration summary: "
                f"total={result.illustration_result['total_tasks']} "
                f"generated={result.illustration_result['generated']} "
                f"skipped={result.illustration_result['skipped']} "
                f"failed={result.illustration_result['failed']} "
                f"cover_status={result.illustration_result['cover']['status']} "
                f"manifest={result.illustration_result['manifest_path']}"
            )
    except Exception as error:
        print(f"Pipeline failed: {error}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
