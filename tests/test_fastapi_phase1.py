import os
import tempfile
import unittest
from unittest.mock import patch

try:
    from tests.asgi_test_client import ASGITestClient as TestClient
except ModuleNotFoundError:  # pragma: no cover - local env without FastAPI
    TestClient = None

try:
    from app.main import create_app
except ModuleNotFoundError:  # pragma: no cover - local env without FastAPI
    create_app = None

try:
    from generators.story.story_model import STORY_PAGE_COUNT, Page, Story, VocabularyEntry
except ModuleNotFoundError:  # pragma: no cover - local env without pydantic
    STORY_PAGE_COUNT = None
    Page = None
    Story = None
    VocabularyEntry = None


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


@unittest.skipIf(
    TestClient is None
    or create_app is None
    or Story is None
    or Page is None
    or STORY_PAGE_COUNT is None
    or VocabularyEntry is None,
    "fastapi/pydantic dependencies are not installed in this environment",
)
class TestFastAPIServerPhase1(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

        self.env_patcher = patch.dict(
            os.environ,
            {
                "MORETALE_API_KEY": "test-api-key",
                "MORETALE_OUTPUTS_DIR": self.tmp_dir.name,
                "MORETALE_RATE_LIMIT_POST_STORIES_PER_MIN": "100",
            },
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        self.client = TestClient(create_app())
        self.headers = {"X-API-Key": "test-api-key"}

    @staticmethod
    def _build_create_payload() -> dict:
        return {
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

    def test_healthz_returns_200(self) -> None:
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "ok")

    def test_post_stories_requires_api_key(self) -> None:
        response = self.client.post("/api/stories/", json=self._build_create_payload())
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"]["code"], "UNAUTHORIZED")

    def test_post_stories_returns_202_with_required_fields(self) -> None:
        story_id = "20260221_120000_story_mina-friendship"
        with patch(
            "app.services.generation_pipeline.generate_story",
            return_value=(_build_fake_story(), "gemini-2.5-flash"),
        ):
            with patch("app.services.story_orchestrator.make_story_id", return_value=story_id):
                response = self.client.post(
                    "/api/stories/",
                    json=self._build_create_payload(),
                    headers=self.headers,
                )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["id"], story_id)
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["status_url"], f"/api/stories/{story_id}")
        self.assertEqual(body["result_url"], f"/api/stories/{story_id}/result")

    def test_background_success_updates_to_completed_and_result(self) -> None:
        story_id = "20260221_120001_story_mina-friendship"
        with patch(
            "app.services.generation_pipeline.generate_story",
            return_value=(_build_fake_story(), "gemini-2.5-flash"),
        ):
            with patch("app.services.story_orchestrator.make_story_id", return_value=story_id):
                create_response = self.client.post(
                    "/api/stories/",
                    json=self._build_create_payload(),
                    headers=self.headers,
                )
        self.assertEqual(create_response.status_code, 202)

        status_response = self.client.get(
            f"/api/stories/{story_id}",
            headers=self.headers,
        )
        self.assertEqual(status_response.status_code, 200)
        status_body = status_response.json()
        self.assertEqual(status_body["status"], "completed")
        self.assertIsNotNone(status_body["result"])
        self.assertTrue(
            status_body["result"]["story_json_url"].startswith(
                f"/static/outputs/{story_id}/story_"
            )
        )

        result_response = self.client.get(
            f"/api/stories/{story_id}/result",
            headers=self.headers,
        )
        self.assertEqual(result_response.status_code, 200)
        result_body = result_response.json()
        self.assertEqual(result_body["id"], story_id)
        self.assertEqual(len(result_body["pages"]), STORY_PAGE_COUNT)
        self.assertIsNone(result_body["pages"][0]["audio_primary_url"])
        self.assertIsNone(result_body["pages"][0]["audio_secondary_url"])
        self.assertIsNone(result_body["pages"][0]["illustration_url"])
        self.assertEqual(result_body["pages"][0]["vocabulary"][0]["primary_word"], "dragon")
        self.assertEqual(
            result_body["pages"][0]["vocabulary"][0]["pronunciation"]["primary_status"],
            "not_requested",
        )
        self.assertIsNone(
            result_body["pages"][0]["vocabulary"][0]["pronunciation"]["primary_url"]
        )

    def test_get_story_not_found_returns_404(self) -> None:
        response = self.client.get(
            "/api/stories/non-existent-story-id",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["error"]["code"], "STORY_NOT_FOUND")

    def test_generation_failure_is_saved_in_meta(self) -> None:
        story_id = "20260221_120002_story_mina-friendship"
        with patch(
            "app.services.generation_pipeline.generate_story",
            side_effect=RuntimeError("simulated failure"),
        ):
            with patch("app.services.story_orchestrator.make_story_id", return_value=story_id):
                response = self.client.post(
                    "/api/stories/",
                    json=self._build_create_payload(),
                    headers=self.headers,
                )
        self.assertEqual(response.status_code, 202)

        status_response = self.client.get(
            f"/api/stories/{story_id}",
            headers=self.headers,
        )
        self.assertEqual(status_response.status_code, 200)
        status_body = status_response.json()
        self.assertEqual(status_body["status"], "failed")
        self.assertEqual(status_body["error"]["code"], "GENERATION_FAILED")


if __name__ == "__main__":
    unittest.main()
