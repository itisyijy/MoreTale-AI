import os
import tempfile
import unittest
from unittest.mock import patch

try:
    from tests.asgi_test_client import ASGITestClient as TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None

try:
    from app.main import create_app
except ModuleNotFoundError:  # pragma: no cover
    create_app = None

try:
    from app.services.rate_limiter import post_stories_rate_limiter
except ModuleNotFoundError:  # pragma: no cover
    post_stories_rate_limiter = None

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
    or post_stories_rate_limiter is None
    or Page is None
    or Story is None
    or STORY_PAGE_COUNT is None
    or VocabularyEntry is None,
    "fastapi/pydantic dependencies are not installed in this environment",
)
class TestFastAPIServerPhase3Hardening(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

        self.env_patcher = patch.dict(
            os.environ,
            {
                "MORETALE_API_KEY": "key-a,key-b",
                "MORETALE_OUTPUTS_DIR": self.tmp_dir.name,
                "MORETALE_RATE_LIMIT_POST_STORIES_PER_MIN": "5",
                "MORETALE_THEME_MAX_LEN": "120",
                "MORETALE_EXTRA_PROMPT_MAX_LEN": "500",
                "MORETALE_CHILD_NAME_MAX_LEN": "40",
                "MORETALE_ALLOWED_STORY_MODELS": "gemini-2.5-flash",
                "MORETALE_ALLOWED_TTS_MODELS": "gemini-2.5-flash-preview-tts",
                "MORETALE_ALLOWED_ILLUSTRATION_MODELS": "gemini-2.5-flash-image",
                "MORETALE_ALLOWED_LANGUAGES": "Korean,English,Japanese,Chinese,Spanish,Vietnamese,French,German",
            },
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        post_stories_rate_limiter.reset()
        self.client = TestClient(create_app())
        self.headers_a = {"X-API-Key": "key-a"}
        self.headers_b = {"X-API-Key": "key-b"}

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

    def _post_story(self, story_id: str, payload: dict, headers: dict[str, str]):
        with patch(
            "app.services.generation_pipeline.generate_story",
            return_value=(_build_fake_story(), "gemini-2.5-flash"),
        ):
            with patch("app.services.story_orchestrator.make_story_id", return_value=story_id):
                return self.client.post(
                    "/api/stories/",
                    json=payload,
                    headers=headers,
                )

    def test_x_request_id_header_on_success_and_error(self) -> None:
        success_response = self.client.get("/healthz")
        self.assertEqual(success_response.status_code, 200)
        self.assertTrue(success_response.headers.get("X-Request-ID"))

        error_response = self.client.post(
            "/api/stories/",
            json=self._base_payload(),
        )
        self.assertEqual(error_response.status_code, 401)
        self.assertTrue(error_response.headers.get("X-Request-ID"))

    def test_rate_limit_6th_post_returns_429(self) -> None:
        payload = self._base_payload()
        with patch("app.services.rate_limiter.time.time", return_value=1700000000.0):
            for index in range(1, 6):
                response = self._post_story(
                    story_id=f"20260221_14000{index}_story_mina",
                    payload=payload,
                    headers=self.headers_a,
                )
                self.assertEqual(response.status_code, 202)

            blocked_response = self._post_story(
                story_id="20260221_140006_story_mina",
                payload=payload,
                headers=self.headers_a,
            )
        self.assertEqual(blocked_response.status_code, 429)
        self.assertEqual(blocked_response.json()["error"]["code"], "RATE_LIMIT_EXCEEDED")

    def test_rate_limit_counter_is_isolated_per_api_key(self) -> None:
        payload = self._base_payload()
        with patch("app.services.rate_limiter.time.time", return_value=1700000000.0):
            for index in range(1, 6):
                response = self._post_story(
                    story_id=f"20260221_14100{index}_story_mina",
                    payload=payload,
                    headers=self.headers_a,
                )
                self.assertEqual(response.status_code, 202)

            blocked_a = self._post_story(
                story_id="20260221_141006_story_mina",
                payload=payload,
                headers=self.headers_a,
            )
        self.assertEqual(blocked_a.status_code, 429)

        with patch("app.services.rate_limiter.time.time", return_value=1700000000.0):
            allowed_b = self._post_story(
                story_id="20260221_141007_story_mina",
                payload=payload,
                headers=self.headers_b,
            )
        self.assertEqual(allowed_b.status_code, 202)

    def test_invalid_story_model_returns_422(self) -> None:
        payload = self._base_payload()
        payload["generation"]["story_model"] = "unsupported-model"
        response = self.client.post(
            "/api/stories/",
            json=payload,
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_invalid_language_returns_422(self) -> None:
        payload = self._base_payload()
        payload["primary_lang"] = "Klingon"
        response = self.client.post(
            "/api/stories/",
            json=payload,
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_theme_and_extra_prompt_length_limit_returns_422(self) -> None:
        payload = self._base_payload()
        payload["theme"] = "A" * 121
        payload["extra_prompt"] = "B" * 501
        response = self.client.post(
            "/api/stories/",
            json=payload,
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_normal_valid_request_still_returns_202(self) -> None:
        response = self._post_story(
            story_id="20260221_142001_story_mina",
            payload=self._base_payload(),
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 202)

    def test_phase2_fields_remain_in_result_payload(self) -> None:
        story_id = "20260221_142002_story_mina"
        create_response = self._post_story(
            story_id=story_id,
            payload=self._base_payload(),
            headers=self.headers_a,
        )
        self.assertEqual(create_response.status_code, 202)

        result_response = self.client.get(
            f"/api/stories/{story_id}/result",
            headers=self.headers_a,
        )
        self.assertEqual(result_response.status_code, 200)
        body = result_response.json()
        self.assertIn("assets", body)
        self.assertIn("has_partial_failures", body["assets"])
        self.assertIn("cover", body["assets"])
        self.assertIn("audio_primary_status", body["pages"][0])
        self.assertIn("audio_secondary_status", body["pages"][0])
        self.assertIn("illustration_status", body["pages"][0])
        self.assertIn("vocabulary", body["pages"][0])
        self.assertIn("pronunciation", body["pages"][0]["vocabulary"][0])


    def test_iso_language_codes_are_accepted_and_normalized(self) -> None:
        iso_pairs = [
            ("ko", "en"), ("en", "ko"), ("vi", "ko"), ("ja", "ko"),
            ("zh", "ko"), ("es", "ko"), ("fr", "ko"), ("de", "ko"),
        ]
        for i, (primary, secondary) in enumerate(iso_pairs):
            payload = self._base_payload()
            payload["primary_lang"] = primary
            payload["secondary_lang"] = secondary
            with patch("app.services.rate_limiter.time.time", return_value=1700000000.0 + i * 60):
                response = self._post_story(
                    story_id=f"20260221_145{i:03d}_story_iso",
                    payload=payload,
                    headers=self.headers_a,
                )
            self.assertEqual(
                response.status_code, 202,
                f"ISO code '{primary}' should be accepted, got {response.status_code}",
            )
            self.assertIn("id", response.json())

    def test_iso_language_code_case_insensitive(self) -> None:
        for i, (primary, secondary) in enumerate([("KO", "en"), ("EN", "ko")]):
            payload = self._base_payload()
            payload["primary_lang"] = primary
            payload["secondary_lang"] = secondary
            response = self._post_story(
                story_id=f"20260221_146{i:03d}_story_iso_upper",
                payload=payload,
                headers=self.headers_a,
            )
            self.assertEqual(
                response.status_code, 202,
                f"Uppercase ISO code '{primary}' should be accepted",
            )

    def test_full_language_names_still_work(self) -> None:
        for i, (primary, secondary) in enumerate([
            ("Korean", "Vietnamese"),
            ("English", "Japanese"),
        ]):
            payload = self._base_payload()
            payload["primary_lang"] = primary
            payload["secondary_lang"] = secondary
            response = self._post_story(
                story_id=f"20260221_147{i:03d}_story_fullname",
                payload=payload,
                headers=self.headers_a,
            )
            self.assertEqual(
                response.status_code, 202,
                f"Full language name '{primary}' should still work",
            )

    def test_invalid_language_code_returns_422(self) -> None:
        for invalid_code in ["kk", "xx"]:
            payload = self._base_payload()
            payload["primary_lang"] = invalid_code
            response = self.client.post(
                "/api/stories/",
                json=payload,
                headers=self.headers_a,
            )
            self.assertEqual(
                response.status_code, 422,
                f"Invalid code '{invalid_code}' should return 422",
            )
            self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
