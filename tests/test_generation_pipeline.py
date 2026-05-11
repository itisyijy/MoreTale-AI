import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.generation_pipeline import (
    StoryPipelineRequest,
    build_pipeline_request_from_story_request,
    generate_story,
    run_story_generation_pipeline,
)
from app.schemas.story import StoryCreateRequest
from generators.critic.critic_model import CriticIssue, CriticResult


def _build_request(**overrides) -> StoryPipelineRequest:
    payload = {
        "child_name": "Mina",
        "child_age": 5,
        "primary_lang": "Korean",
        "secondary_lang": "English",
        "theme": "Friendship",
        "extra_prompt": "Include a dragon",
        "include_style_guide": False,
        "story_model": "gemini-2.5-flash",
        "enable_quiz": False,
        "quiz_model": "gemini-2.5-flash",
        "quiz_question_count": 5,
        "enable_tts": False,
        "tts_model": "gemini-2.5-flash-preview-tts",
        "tts_voice": "Achernar",
        "tts_temperature": 1.0,
        "tts_request_interval_sec": 10.0,
        "enable_illustration": False,
        "enable_cover_illustration": True,
        "illustration_model": "gemini-2.5-flash-image",
        "illustration_aspect_ratio": "1:1",
        "illustration_cover_aspect_ratio": "5:4",
        "illustration_request_interval_sec": 1.0,
        "illustration_skip_existing": True,
    }
    payload.update(overrides)
    return StoryPipelineRequest(**payload)


def _fake_story(title: str = "Test Story") -> SimpleNamespace:
    return SimpleNamespace(
        title_primary=title,
        model_dump_json=lambda indent=4: f'{{"title_primary":"{title}","pages":[]}}',
    )


class TestGenerationPipeline(unittest.TestCase):
    def test_generate_story_uses_story_generator_supported_arguments(self):
        request = _build_request()
        fake_story = _fake_story()

        class FakeStoryGenerator:
            def __init__(self, model_name: str, include_style_guide: bool):
                self.model_name = model_name
                self.include_style_guide = include_style_guide

            def generate_story(
                self,
                child_name: str,
                primary_lang: str,
                secondary_lang: str,
                theme: str,
                extra_prompt: str = "",
                child_age: int | None = None,
            ):
                return fake_story

        with patch("generators.story.story_generator.StoryGenerator", FakeStoryGenerator):
            story, model = generate_story(request)

        self.assertIs(story, fake_story)
        self.assertEqual(model, "gemini-2.5-flash")

    def test_style_guide_flag_is_normalized_to_true(self):
        request = StoryCreateRequest.model_validate(
            {
                "child_name": "Mina",
                "child_age": 5,
                "primary_lang": "Korean",
                "secondary_lang": "English",
                "theme": "Friendship",
                "extra_prompt": "Include a dragon",
                "include_style_guide": False,
                "generation": {
                    "story_model": "gemini-2.5-flash",
                    "enable_tts": False,
                    "enable_illustration": False,
                },
            }
        )

        pipeline_request = build_pipeline_request_from_story_request(request)

        self.assertTrue(request.include_style_guide)
        self.assertTrue(pipeline_request.include_style_guide)

    def test_build_pipeline_request_carries_critic_options(self):
        request = StoryCreateRequest.model_validate(
            {
                "child_name": "Mina",
                "child_age": 5,
                "primary_lang": "Korean",
                "secondary_lang": "English",
                "generation": {
                    "story_model": "gemini-2.5-flash",
                    "enable_critic": True,
                    "critic_model": "gemini-2.5-flash",
                    "critic_max_retries": 1,
                },
            }
        )

        pipeline_request = build_pipeline_request_from_story_request(request)

        self.assertTrue(pipeline_request.enable_critic)
        self.assertEqual(pipeline_request.critic_model, "gemini-2.5-flash")
        self.assertEqual(pipeline_request.critic_max_retries, 1)

    def test_invalid_critic_model_is_rejected(self):
        with self.assertRaises(ValueError):
            StoryCreateRequest.model_validate(
                {
                    "child_name": "Mina",
                    "primary_lang": "Korean",
                    "secondary_lang": "English",
                    "generation": {
                        "critic_model": "unsupported-model",
                    },
                }
            )

    def test_critic_disabled_does_not_call_critic(self):
        request = _build_request(enable_critic=False)
        fake_story = _fake_story()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "app.services.generation_pipeline.generate_story",
                return_value=(fake_story, "gemini-2.5-flash"),
            ) as mocked_story:
                with patch(
                    "app.services.generation_pipeline.generate_critic",
                ) as mocked_critic:
                    result = run_story_generation_pipeline(
                        request=request,
                        output_dir_factory=lambda story, model: Path(tmp_dir) / "run",
                        strict_assets=True,
                    )

        mocked_story.assert_called_once()
        mocked_critic.assert_not_called()
        self.assertEqual(result.critic_results, [])

    def test_critic_ok_does_not_regenerate_story(self):
        request = _build_request(enable_critic=True)
        fake_story = _fake_story()
        ok_result = CriticResult(overall_verdict="ok")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "app.services.generation_pipeline.generate_story",
                return_value=(fake_story, "gemini-2.5-flash"),
            ) as mocked_story:
                with patch(
                    "app.services.generation_pipeline.generate_critic",
                    return_value=ok_result,
                ) as mocked_critic:
                    result = run_story_generation_pipeline(
                        request=request,
                        output_dir_factory=lambda story, model: Path(tmp_dir) / "run",
                        strict_assets=True,
                    )

        mocked_story.assert_called_once()
        mocked_critic.assert_called_once()
        self.assertEqual(result.critic_results, [ok_result])

    def test_critic_revise_then_ok_regenerates_with_feedback(self):
        request = _build_request(enable_critic=True, critic_max_retries=2)
        first_story = _fake_story("First Story")
        revised_story = _fake_story("Revised Story")
        revise_result = CriticResult(
            overall_verdict="revise",
            issues=[
                CriticIssue(
                    page=3,
                    category="image_text_mismatch",
                    severity="major",
                    evidence="missing kite",
                    explanation="The page text names a kite but the prompt omits it.",
                    suggested_fix="Add the kite to the illustration prompt.",
                )
            ],
            global_notes=["Keep the resolution grounded."],
        )
        ok_result = CriticResult(overall_verdict="ok")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "app.services.generation_pipeline.generate_story",
                side_effect=[
                    (first_story, "gemini-2.5-flash"),
                    (revised_story, "gemini-2.5-flash"),
                ],
            ) as mocked_story:
                with patch(
                    "app.services.generation_pipeline.generate_critic",
                    side_effect=[revise_result, ok_result],
                ) as mocked_critic:
                    result = run_story_generation_pipeline(
                        request=request,
                        output_dir_factory=lambda story, model: Path(tmp_dir) / "run",
                        strict_assets=True,
                    )

        self.assertEqual(mocked_story.call_count, 2)
        self.assertEqual(mocked_critic.call_count, 2)
        revised_request = mocked_story.call_args_list[1].args[0]
        self.assertIn("CRITIC FEEDBACK", revised_request.extra_prompt)
        self.assertIn("image_text_mismatch", revised_request.extra_prompt)
        self.assertIn("Keep the resolution grounded.", revised_request.extra_prompt)
        self.assertIs(result.story, revised_story)
        self.assertEqual(result.critic_results, [revise_result, ok_result])

    def test_critic_revise_stops_at_max_retries(self):
        request = _build_request(enable_critic=True, critic_max_retries=1)
        first_story = _fake_story("First Story")
        final_story = _fake_story("Final Story")
        revise_result = CriticResult(
            overall_verdict="revise",
            issues=[
                CriticIssue(
                    page=None,
                    category="protagonist_agency",
                    severity="major",
                    evidence="The ending happens by chance.",
                    explanation="The child needs one active choice for the outcome.",
                    suggested_fix="Let the child choose the final action.",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "app.services.generation_pipeline.generate_story",
                side_effect=[
                    (first_story, "gemini-2.5-flash"),
                    (final_story, "gemini-2.5-flash"),
                ],
            ) as mocked_story:
                with patch(
                    "app.services.generation_pipeline.generate_critic",
                    side_effect=[revise_result, revise_result],
                ) as mocked_critic:
                    result = run_story_generation_pipeline(
                        request=request,
                        output_dir_factory=lambda story, model: Path(tmp_dir) / "run",
                        strict_assets=True,
                    )

        self.assertEqual(mocked_story.call_count, 2)
        self.assertEqual(mocked_critic.call_count, 2)
        self.assertIs(result.story, final_story)
        self.assertEqual(result.critic_results, [revise_result, revise_result])

    def test_non_strict_pipeline_captures_tts_error_and_continues(self):
        request = _build_request(enable_tts=True, enable_illustration=True)
        fake_story = _fake_story()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "app.services.generation_pipeline.generate_story",
                return_value=(fake_story, "gemini-2.5-flash"),
            ):
                with patch(
                    "app.services.generation_pipeline.generate_tts",
                    side_effect=RuntimeError("tts unavailable"),
                ):
                    with patch(
                        "app.services.generation_pipeline.generate_illustrations",
                        return_value={"total_tasks": 1, "generated": 1, "skipped": 0, "failed": 0, "cover": {"status": "generated"}, "manifest_path": "manifest.json"},
                    ) as mocked_illustrations:
                        result = run_story_generation_pipeline(
                            request=request,
                            output_dir_factory=lambda story, model: Path(tmp_dir) / "run",
                            strict_assets=False,
                        )

        self.assertEqual(result.service_errors["tts"], "tts unavailable")
        self.assertIsNone(result.service_errors["quiz"])
        self.assertIsNotNone(result.illustration_result)
        mocked_illustrations.assert_called_once()

    def test_pipeline_generates_quiz_when_enabled(self):
        request = _build_request(enable_quiz=True)
        fake_story = _fake_story()
        fake_quiz = SimpleNamespace(
            model_dump_json=lambda indent=4: '{"story_id":"run","question_count":5,"questions":[]}',
            model_dump=lambda mode="json": {"story_id": "run", "question_count": 5},
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "app.services.generation_pipeline.generate_story",
                return_value=(fake_story, "gemini-2.5-flash"),
            ):
                with patch(
                    "app.services.generation_pipeline.generate_quiz",
                    return_value=(fake_quiz, "gemini-2.5-flash"),
                ) as mocked_quiz:
                    result = run_story_generation_pipeline(
                        request=request,
                        output_dir_factory=lambda story, model: Path(tmp_dir) / "run",
                        strict_assets=True,
                    )
                    quiz_json_exists = (
                        result.quiz_json_path is not None
                        and result.quiz_json_path.is_file()
                    )

        mocked_quiz.assert_called_once()
        self.assertIsNotNone(result.quiz_json_path)
        self.assertTrue(quiz_json_exists)
        self.assertIs(result.quiz_result, fake_quiz)

    def test_non_strict_pipeline_captures_quiz_error_and_continues(self):
        request = _build_request(enable_quiz=True)
        fake_story = _fake_story()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "app.services.generation_pipeline.generate_story",
                return_value=(fake_story, "gemini-2.5-flash"),
            ):
                with patch(
                    "app.services.generation_pipeline.generate_quiz",
                    side_effect=RuntimeError("quiz unavailable"),
                ):
                    result = run_story_generation_pipeline(
                        request=request,
                        output_dir_factory=lambda story, model: Path(tmp_dir) / "run",
                        strict_assets=False,
                    )

        self.assertEqual(result.service_errors["quiz"], "quiz unavailable")
        self.assertIsNone(result.quiz_json_path)

    def test_strict_pipeline_raises_on_quiz_error(self):
        request = _build_request(enable_quiz=True)
        fake_story = _fake_story()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "app.services.generation_pipeline.generate_story",
                return_value=(fake_story, "gemini-2.5-flash"),
            ):
                with patch(
                    "app.services.generation_pipeline.generate_quiz",
                    side_effect=RuntimeError("quiz unavailable"),
                ):
                    with self.assertRaises(RuntimeError):
                        run_story_generation_pipeline(
                            request=request,
                            output_dir_factory=lambda story, model: Path(tmp_dir) / "run",
                            strict_assets=True,
                        )

    def test_strict_pipeline_raises_on_missing_tts_key(self):
        request = _build_request(enable_tts=True)
        fake_story = _fake_story()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "app.services.generation_pipeline.generate_story",
                return_value=(fake_story, "gemini-2.5-flash"),
            ):
                with patch.dict(os.environ, {}, clear=True):
                    with self.assertRaises(RuntimeError):
                        run_story_generation_pipeline(
                            request=request,
                            output_dir_factory=lambda story, model: Path(tmp_dir) / "run",
                            strict_assets=True,
                        )


if __name__ == "__main__":
    unittest.main()
