import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("MORETALE_STORY_PAGE_COUNT", "3")

from generators.story.story_model import Page, Story

try:
    from tests.asgi_test_client import ASGITestClient as TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None

try:
    from app.main import create_app
except ModuleNotFoundError:  # pragma: no cover
    create_app = None


@unittest.skipIf(
    TestClient is None or create_app is None,
    "fastapi/httpx dependencies are not installed in this environment",
)
class TestInternalAIAsyncAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

        self.env_patcher = patch.dict(
            os.environ,
            {
                "MORETALE_API_KEY": "test-api-key",
                "MORETALE_OUTPUTS_DIR": self.tmp_dir.name,
                "MORETALE_STORY_PAGE_COUNT": "3",
            },
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        self.client = TestClient(create_app())
        self.headers = {"X-API-Key": "test-api-key"}
        self.callback_url = "https://backend.test/internal/ai/callback"

    def test_story_job_returns_202_and_result_url(self) -> None:
        story_result = {
            "title": "Mina's Adventure",
            "childName": "Mina",
            "primaryLanguage": "ko",
            "secondaryLanguage": "en",
            "slides": [],
        }

        with patch(
            "app.services.internal_ai_jobs.run_story_job",
            return_value=story_result,
        ), patch(
            "app.services.internal_ai_jobs.notify_callback",
            new_callable=AsyncMock,
        ) as notify:
            response = self.client.post(
                "/internal/ai/story/jobs",
                json={
                    "callbackUrl": self.callback_url,
                    "prompt": "friendship",
                    "childName": "Mina",
                    "primaryLanguage": "ko",
                    "secondaryLanguage": "en",
                },
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["type"], "story")
        self.assertEqual(body["status"], "queued")
        self.assertTrue(body["jobId"])
        self.assertEqual(body["callbackUrl"], self.callback_url)
        self.assertEqual(body["statusUrl"], f"/internal/ai/jobs/{body['jobId']}")
        self.assertEqual(
            body["resultUrl"],
            f"/internal/ai/story/jobs/{body['jobId']}/result",
        )
        notify.assert_awaited_once()

        status_response = self.client.get(body["statusUrl"], headers=self.headers)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "completed")

        result_response = self.client.get(body["resultUrl"], headers=self.headers)
        self.assertEqual(result_response.status_code, 200)
        result_body = result_response.json()
        self.assertEqual(result_body["status"], "completed")
        self.assertEqual(result_body["data"], story_result)

    def test_tts_quiz_and_vocab_job_creation(self) -> None:
        cases = [
            (
                "/internal/ai/tts/jobs",
                "tts",
                {"callbackUrl": self.callback_url, "text": "hello", "language": "en-US"},
                "run_tts_job",
                {"audioUrl": "/static/outputs/job/tts.wav"},
            ),
            (
                "/internal/ai/quiz/jobs",
                "quiz",
                {
                    "callbackUrl": self.callback_url,
                    "storyId": "story-1",
                    "story": {"title_primary": "t", "title_secondary": "t", "author_name": "a", "primary_language": "Korean", "secondary_language": "English", "image_style": "s", "main_character_design": "c", "pages": [{"page_number": i, "text_primary": "p", "text_secondary": "s", "illustration_prompt": "i"} for i in range(1, 33)]},
                },
                "run_quiz_job",
                {"questions": []},
            ),
            (
                "/internal/ai/vocab/jobs",
                "vocab",
                {
                    "callbackUrl": self.callback_url,
                    "storyId": "story-1",
                    "slides": [{"order": 1, "textKr": "안녕 친구", "textNative": "hello friend"}],
                },
                "run_vocab_job",
                {"entries": []},
            ),
        ]

        for path, job_type, payload, runner_name, result in cases:
            with self.subTest(job_type=job_type):
                with patch(
                    f"app.services.internal_ai_jobs.{runner_name}",
                    return_value=result,
                ), patch(
                    "app.services.internal_ai_jobs.notify_callback",
                    new_callable=AsyncMock,
                ):
                    response = self.client.post(path, json=payload, headers=self.headers)

                self.assertEqual(response.status_code, 202)
                body = response.json()
                self.assertEqual(body["type"], job_type)
                result_response = self.client.get(body["resultUrl"], headers=self.headers)
                self.assertEqual(result_response.status_code, 200)
                self.assertEqual(result_response.json()["data"], result)

    def test_failed_job_is_persisted_for_callback_and_result(self) -> None:
        seen_jobs = []

        async def capture(job):
            seen_jobs.append(job)

        with patch(
            "app.services.internal_ai_jobs.run_vocab_job",
            side_effect=RuntimeError("simulated failure"),
        ), patch(
            "app.services.internal_ai_jobs.notify_callback",
            side_effect=capture,
        ):
            response = self.client.post(
                "/internal/ai/vocab/jobs",
                json={
                    "callbackUrl": self.callback_url,
                    "slides": [{"order": 1, "textKr": "안녕", "textNative": "hello"}],
                },
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(seen_jobs), 1)
        self.assertEqual(seen_jobs[0]["status"], "failed")
        self.assertEqual(seen_jobs[0]["error"]["code"], "AI_JOB_FAILED")

        result_response = self.client.get(response.json()["resultUrl"], headers=self.headers)
        self.assertEqual(result_response.status_code, 200)
        result_body = result_response.json()
        self.assertEqual(result_body["status"], "failed")
        self.assertEqual(result_body["error"]["code"], "AI_JOB_FAILED")


class TestInternalAIStoryRunner(unittest.TestCase):
    def test_story_job_generates_bundle_strictly_and_returns_asset_urls(self) -> None:
        from app.services.internal_ai_runners import run_story_job

        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(
            os.environ,
            {"MORETALE_OUTPUTS_DIR": tmp_dir, "MORETALE_STORY_PAGE_COUNT": "3"},
            clear=False,
        ):
            story = Story(
                title_primary="제목",
                title_secondary="Title",
                author_name="Mina",
                primary_language="Korean",
                secondary_language="English",
                image_style="storybook",
                main_character_design="child",
                pages=[
                    Page(
                        page_number=index,
                        text_primary=f"문장 {index}",
                        text_secondary=f"Sentence {index}",
                        illustration_prompt=f"Scene {index}",
                    )
                    for index in range(1, 3)
                ],
            )
            captured = {}

            def fake_pipeline(request, output_dir_factory, strict_assets):
                captured["request"] = request
                captured["strict_assets"] = strict_assets
                output_dir = output_dir_factory(story, request.story_model)
                (output_dir / "illustrations").mkdir(parents=True, exist_ok=True)
                (output_dir / "audio" / "01_korean").mkdir(parents=True, exist_ok=True)
                (output_dir / "audio" / "02_english").mkdir(parents=True, exist_ok=True)
                for page_number in range(1, 3):
                    (output_dir / "illustrations" / f"page_{page_number:02d}.png").write_bytes(
                        b"image"
                    )
                    (
                        output_dir
                        / "audio"
                        / "01_korean"
                        / f"page_{page_number:02d}_primary.wav"
                    ).write_bytes(b"RIFF")
                    (
                        output_dir
                        / "audio"
                        / "02_english"
                        / f"page_{page_number:02d}_secondary.wav"
                    ).write_bytes(b"RIFF")
                return SimpleNamespace(story=story, output_dir=output_dir)

            with patch(
                "app.services.internal_ai_runners.run_story_generation_pipeline",
                side_effect=fake_pipeline,
            ):
                payload = run_story_job(
                    "story-job-1",
                    {
                        "callbackUrl": "https://backend.test/internal/ai/callback",
                        "prompt": "friendship",
                        "childName": "Mina",
                        "primaryLanguage": "ko",
                        "secondaryLanguage": "en",
                    },
                )

        pipeline_request = captured["request"]
        self.assertTrue(pipeline_request.enable_tts)
        self.assertTrue(pipeline_request.enable_illustration)
        self.assertTrue(pipeline_request.enable_cover_illustration)
        self.assertTrue(captured["strict_assets"])
        self.assertEqual([slide["order"] for slide in payload["slides"]], [0, 1])
        self.assertEqual(
            payload["slides"][0]["imageUrl"],
            "/static/outputs/story-job-1/illustrations/page_01.png",
        )
        self.assertEqual(
            payload["slides"][0]["audioUrlKr"],
            "/static/outputs/story-job-1/audio/01_korean/page_01_primary.wav",
        )
        self.assertEqual(
            payload["slides"][0]["audioUrlNative"],
            "/static/outputs/story-job-1/audio/02_english/page_01_secondary.wav",
        )

    def test_story_job_uploads_assets_to_gcs_when_enabled(self) -> None:
        from app.services.internal_ai_runners import run_story_job

        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(
            os.environ,
            {
                "MORETALE_OUTPUTS_DIR": tmp_dir,
                "MORETALE_STORY_PAGE_COUNT": "3",
                "MORETALE_STORAGE_BACKEND": "gcs",
                "MORETALE_GCS_BUCKET": "moretale-assets",
                "MORETALE_GCS_KEY_PREFIX": "generated",
            },
            clear=False,
        ):
            story = Story(
                title_primary="제목",
                title_secondary="Title",
                author_name="Mina",
                primary_language="Korean",
                secondary_language="English",
                image_style="storybook",
                main_character_design="child",
                pages=[
                    Page(
                        page_number=1,
                        text_primary="문장",
                        text_secondary="Sentence",
                        illustration_prompt="Scene",
                    )
                ],
            )

            def fake_pipeline(request, output_dir_factory, strict_assets):
                output_dir = output_dir_factory(story, request.story_model)
                (output_dir / "illustrations").mkdir(parents=True, exist_ok=True)
                (output_dir / "audio" / "01_korean").mkdir(parents=True, exist_ok=True)
                (output_dir / "audio" / "02_english").mkdir(parents=True, exist_ok=True)
                (output_dir / "illustrations" / "page_01.png").write_bytes(b"image")
                (
                    output_dir / "audio" / "01_korean" / "page_01_primary.wav"
                ).write_bytes(b"RIFF")
                (
                    output_dir / "audio" / "02_english" / "page_01_secondary.wav"
                ).write_bytes(b"RIFF")
                return SimpleNamespace(story=story, output_dir=output_dir)

            with patch(
                "app.services.internal_ai_runners.run_story_generation_pipeline",
                side_effect=fake_pipeline,
            ), patch("app.services.storage_backend._build_gcs_client") as client_factory:
                payload = run_story_job(
                    "story-job-1",
                    {
                        "callbackUrl": "https://backend.test/internal/ai/callback",
                        "prompt": "friendship",
                        "childName": "Mina",
                        "primaryLanguage": "ko",
                        "secondaryLanguage": "en",
                    },
                )

        bucket = client_factory.return_value.bucket.return_value
        self.assertEqual(bucket.blob.call_count, 3)
        self.assertEqual(
            payload["slides"][0]["imageUrl"],
            "https://storage.googleapis.com/moretale-assets/generated/story-job-1/illustrations/page_01.png",
        )
        self.assertEqual(
            payload["slides"][0]["audioUrlKr"],
            "https://storage.googleapis.com/moretale-assets/generated/story-job-1/audio/01_korean/page_01_primary.wav",
        )


if __name__ == "__main__":
    unittest.main()
