import os
import tempfile
import unittest
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
    from app.services.story_orchestrator import job_store
except ModuleNotFoundError:  # pragma: no cover
    job_store = None

try:
    from generators.story.story_model import STORY_PAGE_COUNT, Page, Story, VocabularyEntry
except ModuleNotFoundError:  # pragma: no cover
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
    or job_store is None
    or Page is None
    or Story is None
    or STORY_PAGE_COUNT is None
    or VocabularyEntry is None,
    "fastapi/pydantic dependencies are not installed in this environment",
)
class TestFastAPIPhase4Cancel(unittest.TestCase):
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

    @staticmethod
    def _base_payload() -> dict:
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

    def _post_story(self, story_id: str):
        with patch(
            "app.services.generation_pipeline.generate_story",
            return_value=(_build_fake_story(), "gemini-2.5-flash"),
        ):
            with patch("app.services.story_orchestrator.make_story_id", return_value=story_id):
                return self.client.post(
                    "/api/stories/",
                    json=self._base_payload(),
                    headers=self.headers,
                )

    def test_delete_queued_job_returns_200_canceled(self) -> None:
        story_id = "20260221_160001_story_mina"
        job_store.initialize_job(story_id=story_id, request_payload=self._base_payload())

        response = self.client.delete(f"/api/stories/{story_id}", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "canceled")

    def test_delete_running_job_returns_200_canceled(self) -> None:
        story_id = "20260221_160002_story_mina"
        job_store.initialize_job(story_id=story_id, request_payload=self._base_payload())
        job_store.mark_running(story_id)

        response = self.client.delete(f"/api/stories/{story_id}", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "canceled")

    def test_delete_completed_job_returns_409(self) -> None:
        story_id = "20260221_160003_story_mina"
        create_response = self._post_story(story_id)
        self.assertEqual(create_response.status_code, 202)

        response = self.client.delete(f"/api/stories/{story_id}", headers=self.headers)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "STORY_CANCEL_NOT_ALLOWED")

    def test_delete_failed_job_returns_409(self) -> None:
        story_id = "20260221_160004_story_mina"
        job_store.initialize_job(story_id=story_id, request_payload=self._base_payload())
        job_store.mark_failed(story_id, error={"code": "ERR", "message": "fail"})

        response = self.client.delete(f"/api/stories/{story_id}", headers=self.headers)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "STORY_CANCEL_NOT_ALLOWED")

    def test_delete_canceled_job_returns_409(self) -> None:
        story_id = "20260221_160005_story_mina"
        job_store.initialize_job(story_id=story_id, request_payload=self._base_payload())
        job_store.mark_canceled(story_id)

        response = self.client.delete(f"/api/stories/{story_id}", headers=self.headers)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "STORY_CANCEL_NOT_ALLOWED")

    def test_delete_nonexistent_job_returns_404(self) -> None:
        response = self.client.delete("/api/stories/no-such-id-xyz", headers=self.headers)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "STORY_NOT_FOUND")

    def test_delete_without_api_key_returns_401(self) -> None:
        story_id = "20260221_160006_story_mina"
        job_store.initialize_job(story_id=story_id, request_payload=self._base_payload())

        response = self.client.delete(f"/api/stories/{story_id}")

        self.assertEqual(response.status_code, 401)

    def test_x_request_id_present_in_cancel_response(self) -> None:
        story_id = "20260221_160007_story_mina"
        job_store.initialize_job(story_id=story_id, request_payload=self._base_payload())

        response = self.client.delete(f"/api/stories/{story_id}", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("X-Request-ID"))


if __name__ == "__main__":
    unittest.main()
