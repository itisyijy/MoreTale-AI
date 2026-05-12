import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

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


if __name__ == "__main__":
    unittest.main()
