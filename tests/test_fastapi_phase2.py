import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("MORETALE_STORY_PAGE_COUNT", "3")

try:
    from tests.asgi_test_client import ASGITestClient as TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None

try:
    from app.main import create_app
except ModuleNotFoundError:  # pragma: no cover
    create_app = None

try:
    from generators.story.story_model import STORY_PAGE_COUNT, Page, Story, VocabularyEntry
except ModuleNotFoundError:  # pragma: no cover
    STORY_PAGE_COUNT = None
    Page = None
    Story = None
    VocabularyEntry = None

try:
    from app.services.job_store import JobStore
    from app.services.storage import get_run_dir, write_story_json
except ModuleNotFoundError:  # pragma: no cover
    JobStore = None
    get_run_dir = None
    write_story_json = None


def _build_fake_story():
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
        pages=pages,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


@unittest.skipIf(
    TestClient is None
    or create_app is None
    or Story is None
    or Page is None
    or STORY_PAGE_COUNT is None
    or VocabularyEntry is None
    or JobStore is None
    or get_run_dir is None
    or write_story_json is None,
    "fastapi/pydantic dependencies are not installed in this environment",
)
class TestFastAPIServerPhase2(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

        self.env_patcher = patch.dict(
            os.environ,
            {
                "MORETALE_API_KEY": "test-api-key",
                "MORETALE_OUTPUTS_DIR": self.tmp_dir.name,
                "MORETALE_RATE_LIMIT_POST_STORIES_PER_MIN": "100",
                "MORETALE_STORY_PAGE_COUNT": "3",
            },
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        self.client = TestClient(create_app())
        self.headers = {"X-API-Key": "test-api-key"}
        self.job_store = JobStore()

    @staticmethod
    def _base_payload() -> dict:
        return {
            "child_name": "Mina",
            "child_age": 5,
            "primary_lang": "Korean",
            "secondary_lang": "English",
            "theme": "Friendship",
            "extra_prompt": "",
            "include_style_guide": False,
            "generation": {
                "story_model": "gemini-2.5-flash",
                "enable_tts": False,
                "enable_illustration": False,
            },
        }

    def _create_story_with_patches(
        self,
        story_id: str,
        payload: dict,
        tts_side_effect=None,
        illustration_side_effect=None,
        story_side_effect=None,
    ):
        story_patch = (
            patch(
                "app.services.generation_pipeline.generate_story",
                side_effect=story_side_effect,
            )
            if story_side_effect is not None
            else patch(
                "app.services.generation_pipeline.generate_story",
                return_value=(_build_fake_story(), "gemini-2.5-flash"),
            )
        )

        with story_patch:
            with patch("app.services.story_orchestrator.make_story_id", return_value=story_id):
                tts_patch = (
                    patch(
                        "app.services.generation_pipeline.generate_tts",
                        side_effect=tts_side_effect,
                    )
                    if tts_side_effect is not None
                    else patch("app.services.generation_pipeline.generate_tts")
                )
                illustration_patch = (
                    patch(
                        "app.services.generation_pipeline.generate_illustrations",
                        side_effect=illustration_side_effect,
                    )
                    if illustration_side_effect is not None
                    else patch(
                        "app.services.generation_pipeline.generate_illustrations"
                    )
                )
                with tts_patch, illustration_patch:
                    return self.client.post(
                        "/api/stories/",
                        json=payload,
                        headers=self.headers,
                    )

    def test_enable_tts_success_populates_audio_status_and_urls(self) -> None:
        payload = self._base_payload()
        payload["generation"]["enable_tts"] = True
        story_id = "20260221_130001_story_mina-friendship"

        def tts_success(*, request, story, output_dir):
            del request, story, output_dir
            run_dir = get_run_dir(story_id)
            primary_dir = run_dir / "audio" / "01_korean"
            secondary_dir = run_dir / "audio" / "02_english"
            primary_dir.mkdir(parents=True, exist_ok=True)
            secondary_dir.mkdir(parents=True, exist_ok=True)
            (primary_dir / "page_01_primary.wav").write_bytes(b"RIFF")
            (secondary_dir / "page_01_secondary.wav").write_bytes(b"RIFF")
            entries = []
            for page_number in range(1, STORY_PAGE_COUNT + 1):
                if page_number == 1:
                    primary_status = "generated"
                    secondary_status = "generated"
                else:
                    primary_status = "skipped_exists"
                    secondary_status = "skipped_exists"

                entries.append(
                    {
                        "page_number": page_number,
                        "language": "Korean",
                        "role": "primary",
                        "path": str(primary_dir / f"page_{page_number:02d}_primary.wav"),
                        "status": primary_status,
                    }
                )
                entries.append(
                    {
                        "page_number": page_number,
                        "language": "English",
                        "role": "secondary",
                        "path": str(secondary_dir / f"page_{page_number:02d}_secondary.wav"),
                        "status": secondary_status,
                    }
                )
            _write_json(
                run_dir / "audio" / "manifest.json",
                {
                    "total_tasks": STORY_PAGE_COUNT * 2,
                    "generated": 2,
                    "skipped": STORY_PAGE_COUNT * 2 - 2,
                    "failed": 0,
                    "entries": entries,
                },
            )
            return {
                "total_tasks": STORY_PAGE_COUNT * 2,
                "generated": 2,
                "skipped": STORY_PAGE_COUNT * 2 - 2,
                "failed": 0,
            }

        create_response = self._create_story_with_patches(
            story_id=story_id,
            payload=payload,
            tts_side_effect=tts_success,
        )
        self.assertEqual(create_response.status_code, 202)

        result_response = self.client.get(
            f"/api/stories/{story_id}/result",
            headers=self.headers,
        )
        self.assertEqual(result_response.status_code, 200)
        body = result_response.json()
        first_page = body["pages"][0]
        self.assertEqual(first_page["audio_primary_status"], "generated")
        self.assertEqual(first_page["audio_secondary_status"], "generated")
        self.assertIsNotNone(first_page["audio_primary_url"])
        self.assertIsNotNone(first_page["audio_secondary_url"])
        self.assertTrue(body["assets"]["tts"]["enabled"])
        self.assertEqual(body["assets"]["tts"]["failed"], 0)

    def test_partial_illustration_failure_is_reported_and_job_completed(self) -> None:
        payload = self._base_payload()
        payload["generation"]["enable_illustration"] = True
        story_id = "20260221_130002_story_mina-friendship"

        def illustration_partial(*, request, story, output_dir):
            del request, story, output_dir
            run_dir = get_run_dir(story_id)
            illustrations_dir = run_dir / "illustrations"
            illustrations_dir.mkdir(parents=True, exist_ok=True)
            (illustrations_dir / "page_02.png").write_bytes(b"\x89PNG")
            _write_json(
                illustrations_dir / "manifest.json",
                {
                    "total_tasks": STORY_PAGE_COUNT,
                    "generated": 1,
                    "skipped": 0,
                    "failed": 1,
                    "entries": [
                        {
                            "page_number": 1,
                            "status": "failed",
                            "error": "illustration api timeout",
                        },
                        {
                            "page_number": 2,
                            "status": "generated",
                            "path": str(illustrations_dir / "page_02.png"),
                        },
                    ],
                },
            )
            return {
                "total_tasks": STORY_PAGE_COUNT,
                "generated": 1,
                "skipped": 0,
                "failed": 1,
            }

        create_response = self._create_story_with_patches(
            story_id=story_id,
            payload=payload,
            illustration_side_effect=illustration_partial,
        )
        self.assertEqual(create_response.status_code, 202)

        status_response = self.client.get(
            f"/api/stories/{story_id}",
            headers=self.headers,
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "completed")

        result_response = self.client.get(
            f"/api/stories/{story_id}/result",
            headers=self.headers,
        )
        self.assertEqual(result_response.status_code, 200)
        body = result_response.json()
        self.assertTrue(body["assets"]["has_partial_failures"])
        self.assertEqual(body["assets"]["cover"]["status"], "missing")
        failed_page = body["pages"][0]
        self.assertEqual(failed_page["illustration_status"], "failed")
        self.assertEqual(failed_page["illustration_error"], "illustration api timeout")

    def test_cover_illustration_is_exposed_in_result_payload(self) -> None:
        payload = self._base_payload()
        payload["generation"]["enable_illustration"] = True
        story_id = "20260221_130002_story_mina-cover"

        def illustration_with_cover(*, request, story, output_dir):
            del request, story, output_dir
            run_dir = get_run_dir(story_id)
            illustrations_dir = run_dir / "illustrations"
            illustrations_dir.mkdir(parents=True, exist_ok=True)
            cover_path = illustrations_dir / "cover.png"
            page_path = illustrations_dir / "page_01.png"
            cover_path.write_bytes(b"\x89PNG")
            page_path.write_bytes(b"\x89PNG")
            _write_json(
                illustrations_dir / "manifest.json",
                {
                    "total_tasks": STORY_PAGE_COUNT + 1,
                    "generated": 2,
                    "skipped": 0,
                    "failed": 0,
                    "entries": [
                        {
                            "asset_type": "cover",
                            "status": "generated",
                            "path": str(cover_path),
                        },
                        {
                            "asset_type": "page",
                            "page_number": 1,
                            "status": "generated",
                            "path": str(page_path),
                        },
                    ],
                },
            )
            return {
                "total_tasks": STORY_PAGE_COUNT + 1,
                "generated": 2,
                "skipped": 0,
                "failed": 0,
                "cover": {
                    "enabled": True,
                    "status": "generated",
                    "error": None,
                    "path": str(cover_path),
                    "aspect_ratio": "5:4",
                },
            }

        create_response = self._create_story_with_patches(
            story_id=story_id,
            payload=payload,
            illustration_side_effect=illustration_with_cover,
        )
        self.assertEqual(create_response.status_code, 202)

        result_response = self.client.get(
            f"/api/stories/{story_id}/result",
            headers=self.headers,
        )
        self.assertEqual(result_response.status_code, 200)
        body = result_response.json()
        self.assertEqual(body["assets"]["cover"]["status"], "generated")
        self.assertEqual(body["assets"]["cover"]["aspect_ratio"], "5:4")
        self.assertTrue(body["assets"]["cover"]["has_cover"])
        self.assertIsNotNone(body["assets"]["cover"]["url"])
        self.assertEqual(body["assets"]["illustrations"]["aspect_ratio"], "1:1")

    def test_tts_service_error_keeps_completed_and_sets_service_error(self) -> None:
        payload = self._base_payload()
        payload["generation"]["enable_tts"] = True
        story_id = "20260221_130003_story_mina-friendship"

        create_response = self._create_story_with_patches(
            story_id=story_id,
            payload=payload,
            tts_side_effect=RuntimeError("tts service unavailable"),
        )
        self.assertEqual(create_response.status_code, 202)

        status_response = self.client.get(
            f"/api/stories/{story_id}",
            headers=self.headers,
        )
        self.assertEqual(status_response.status_code, 200)
        status_body = status_response.json()
        self.assertEqual(status_body["status"], "completed")
        self.assertEqual(
            status_body["result"]["assets"]["tts"]["service_error"],
            "tts service unavailable",
        )
        self.assertTrue(status_body["result"]["assets"]["has_partial_failures"])

    def test_vocabulary_manifest_populates_pronunciation_urls(self) -> None:
        payload = self._base_payload()
        story_id = "20260221_130004_story_mina-vocabulary"

        create_response = self._create_story_with_patches(
            story_id=story_id,
            payload=payload,
        )
        self.assertEqual(create_response.status_code, 202)

        run_dir = get_run_dir(story_id)
        vocabulary_dir = run_dir / "vocabulary" / "page_01"
        vocabulary_dir.mkdir(parents=True, exist_ok=True)
        primary_audio = vocabulary_dir / "page-1-dragon_primary.wav"
        secondary_audio = vocabulary_dir / "page-1-dragon_secondary.wav"
        primary_audio.write_bytes(b"RIFF")
        secondary_audio.write_bytes(b"RIFF")
        _write_json(
            run_dir / "vocabulary" / "manifest.json",
            {
                "entries": [
                    {
                        "page_number": 1,
                        "entry_id": "page-1-dragon",
                        "role": "primary",
                        "path": str(primary_audio),
                        "status": "generated",
                    },
                    {
                        "page_number": 1,
                        "entry_id": "page-1-dragon",
                        "role": "secondary",
                        "path": str(secondary_audio),
                        "status": "generated",
                    },
                ]
            },
        )

        result_response = self.client.get(
            f"/api/stories/{story_id}/result",
            headers=self.headers,
        )
        self.assertEqual(result_response.status_code, 200)
        body = result_response.json()
        pronunciation = body["pages"][0]["vocabulary"][0]["pronunciation"]
        self.assertEqual(pronunciation["primary_status"], "generated")
        self.assertEqual(pronunciation["secondary_status"], "generated")
        self.assertTrue(pronunciation["has_primary_audio"])
        self.assertTrue(pronunciation["has_secondary_audio"])
        self.assertTrue(
            pronunciation["primary_url"].endswith(
                f"/{story_id}/vocabulary/page_01/page-1-dragon_primary.wav"
            )
        )
        self.assertTrue(
            pronunciation["secondary_url"].endswith(
                f"/{story_id}/vocabulary/page_01/page-1-dragon_secondary.wav"
            )
        )

    def test_story_generation_failure_returns_404_on_result(self) -> None:
        payload = self._base_payload()
        story_id = "20260221_130005_story_mina-friendship"

        create_response = self._create_story_with_patches(
            story_id=story_id,
            payload=payload,
            story_side_effect=RuntimeError("story generation failed"),
        )
        self.assertEqual(create_response.status_code, 202)

        status_response = self.client.get(
            f"/api/stories/{story_id}",
            headers=self.headers,
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "failed")

        result_response = self.client.get(
            f"/api/stories/{story_id}/result",
            headers=self.headers,
        )
        self.assertEqual(result_response.status_code, 404)
        self.assertEqual(result_response.json()["error"]["code"], "STORY_RESULT_NOT_FOUND")

    def test_result_returns_409_for_not_ready_statuses(self) -> None:
        payload = self._base_payload()
        queued_id = "20260221_130006_story_queued"
        running_id = "20260221_130007_story_running"
        canceled_id = "20260221_130008_story_canceled"

        self.job_store.initialize_job(story_id=queued_id, request_payload=payload)
        self.job_store.initialize_job(story_id=running_id, request_payload=payload)
        self.job_store.mark_running(story_id=running_id)
        self.job_store.initialize_job(story_id=canceled_id, request_payload=payload)
        self.job_store._set_job_status(story_id=canceled_id, status="canceled")

        for story_id in [queued_id, running_id, canceled_id]:
            response = self.client.get(
                f"/api/stories/{story_id}/result",
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["error"]["code"], "STORY_NOT_READY")

    def test_failed_with_existing_story_json_returns_result(self) -> None:
        payload = self._base_payload()
        story_id = "20260221_130009_story_failed-with-json"
        self.job_store.initialize_job(story_id=story_id, request_payload=payload)
        write_story_json(
            story_id=story_id,
            story=_build_fake_story(),
            story_model="gemini-2.5-flash",
        )
        self.job_store.mark_failed(
            story_id=story_id,
            error={"code": "GENERATION_FAILED", "message": "failed after save"},
        )

        response = self.client.get(
            f"/api/stories/{story_id}/result",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(len(body["pages"]), STORY_PAGE_COUNT)


if __name__ == "__main__":
    unittest.main()
