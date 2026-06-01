import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.schemas.story import StoryResultResponse
from app.services.output_paths import get_run_dir, write_story_json
from app.services.story_result_builder import build_story_result_payload
from generators.story.story_model import STORY_PAGE_COUNT, Page, Story, VocabularyEntry


def _build_fake_story() -> Story:
    pages = [
        Page(
            page_number=page_number,
            text_primary=f"Primary text {page_number}",
            text_secondary=f"Secondary text {page_number}",
            illustration_prompt=f"Illustration prompt {page_number}",
            illustration_scene_prompt=f"Scene prompt {page_number}",
            vocabulary=[
                VocabularyEntry(
                    entry_id=f"page-{page_number}-dragon",
                    primary_word="dragon",
                    secondary_word="용",
                    primary_definition="a large creature from stories",
                    secondary_definition="이야기 속 상상의 큰 동물",
                )
            ],
        )
        for page_number in range(1, STORY_PAGE_COUNT + 1)
    ]
    return Story(
        title_primary="Test Title Primary",
        title_secondary="Test Title Secondary",
        author_name="Test Author",
        primary_language="Korean",
        secondary_language="English",
        image_style="Soft watercolor",
        main_character_design="A child with short hair and green clothes",
        cover_illustration_prompt="Cover prompt",
        pages=pages,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


class TestStoryResultBuilder(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.env_patcher = patch.dict(
            os.environ,
            {
                "MORETALE_OUTPUTS_DIR": self.tmp_dir.name,
                "MORETALE_STORY_PAGE_COUNT": "3",
            },
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

    def test_build_story_result_payload_supports_root_relative_urls(self) -> None:
        story_id = "20260221_160001_story_mina"
        story = _build_fake_story()
        write_story_json(story_id=story_id, story=story, story_model="gemini-2.5-flash")

        run_dir = get_run_dir(story_id)
        _write_json(
            run_dir / "quiz_gemini-2.5-flash.json",
            {
                "story_id": story_id,
                "story_title_primary": "Test Title Primary",
                "story_title_secondary": "Test Title Secondary",
                "primary_language": "Korean",
                "secondary_language": "English",
                "question_count": 1,
                "questions": [],
            },
        )
        primary_audio = run_dir / "audio" / "01_korean" / "page_01_primary.wav"
        secondary_audio = run_dir / "audio" / "02_english" / "page_01_secondary.wav"
        primary_audio.parent.mkdir(parents=True, exist_ok=True)
        secondary_audio.parent.mkdir(parents=True, exist_ok=True)
        primary_audio.write_bytes(b"RIFF")
        secondary_audio.write_bytes(b"RIFF")

        cover_path = run_dir / "illustrations" / "cover.png"
        page_path = run_dir / "illustrations" / "page_01.png"
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        cover_path.write_bytes(b"\x89PNG")
        page_path.write_bytes(b"\x89PNG")

        vocab_primary = run_dir / "vocabulary" / "page_01" / "page-1-dragon_primary.wav"
        vocab_secondary = run_dir / "vocabulary" / "page_01" / "page-1-dragon_secondary.wav"
        vocab_primary.parent.mkdir(parents=True, exist_ok=True)
        vocab_secondary.write_bytes(b"RIFF")
        vocab_primary.write_bytes(b"RIFF")

        _write_json(
            run_dir / "illustrations" / "manifest.json",
            {
                "total_tasks": STORY_PAGE_COUNT + 1,
                "generated": 2,
                "skipped": 0,
                "failed": 0,
                "entries": [
                    {"asset_type": "cover", "status": "generated", "path": str(cover_path)},
                    {
                        "asset_type": "page",
                        "page_number": 1,
                        "status": "generated",
                        "path": str(page_path),
                    },
                ],
            },
        )
        _write_json(
            run_dir / "vocabulary" / "manifest.json",
            {
                "entries": [
                    {
                        "page_number": 1,
                        "entry_id": "page-1-dragon",
                        "role": "primary",
                        "path": str(vocab_primary),
                        "status": "generated",
                    },
                    {
                        "page_number": 1,
                        "entry_id": "page-1-dragon",
                        "role": "secondary",
                        "path": str(vocab_secondary),
                        "status": "generated",
                    },
                ]
            },
        )

        payload = build_story_result_payload(
            story_id=story_id,
            include_tts=True,
            include_illustration=True,
            include_cover_illustration=True,
            illustration_aspect_ratio="1:1",
            cover_aspect_ratio="5:4",
            job_status="completed",
            static_prefix="",
        )

        self.assertEqual(payload["story_json_url"], f"/{story_id}/story_gemini-2.5-flash.json")
        self.assertEqual(payload["quiz_json_url"], f"/{story_id}/quiz_gemini-2.5-flash.json")
        self.assertEqual(payload["pages"][0]["audio_primary_url"], f"/{story_id}/audio/01_korean/page_01_primary.wav")
        self.assertEqual(payload["pages"][0]["illustration_url"], f"/{story_id}/illustrations/page_01.png")
        self.assertEqual(
            payload["pages"][0]["vocabulary"][0]["pronunciation"]["primary_url"],
            f"/{story_id}/vocabulary/page_01/page-1-dragon_primary.wav",
        )
        self.assertEqual(payload["assets"]["cover"]["url"], f"/{story_id}/illustrations/cover.png")
        self.assertEqual(payload["assets"]["illustrations"]["aspect_ratio"], "1:1")
        self.assertEqual(
            payload["critic"],
            {
                "enabled": False,
                "attempts": 0,
                "final_verdict": None,
                "issue_count": 0,
                "results": [],
            },
        )

    def test_build_story_result_payload_omits_quiz_url_when_missing(self) -> None:
        story_id = "20260221_160002_story_mina"
        story = _build_fake_story()
        write_story_json(story_id=story_id, story=story, story_model="gemini-2.5-flash")

        payload = build_story_result_payload(
            story_id=story_id,
            include_tts=False,
            include_illustration=False,
            include_cover_illustration=False,
            illustration_aspect_ratio="1:1",
            cover_aspect_ratio="5:4",
            job_status="completed",
            critic={
                "enabled": True,
                "attempts": 1,
                "final_verdict": "ok",
                "issue_count": 0,
                "results": [{"overall_verdict": "ok", "issues": [], "global_notes": []}],
            },
            static_prefix="",
        )

        self.assertIsNone(payload["quiz_json_url"])
        self.assertTrue(payload["critic"]["enabled"])
        self.assertEqual(payload["critic"]["attempts"], 1)
        self.assertEqual(payload["critic"]["final_verdict"], "ok")
        response = StoryResultResponse.model_validate(payload)
        self.assertTrue(response.critic.enabled)


if __name__ == "__main__":
    unittest.main()
