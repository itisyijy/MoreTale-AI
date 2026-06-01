from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from app.core.config import get_settings
    from app.services.health import HealthCheckError
    from app.services.health import run_health_checks
except ModuleNotFoundError:  # pragma: no cover
    HealthCheckError = None
    get_settings = None
    run_health_checks = None


@unittest.skipIf(
    get_settings is None or run_health_checks is None,
    "dependencies are not installed in this environment",
)
class TestHealthChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.base_env = {
            "MORETALE_API_KEY": "key-a",
            "GEMINI_STORY_API_KEY": "story-key",
            "GEMINI_TTS_API_KEY": "tts-key",
            "NANO_BANANA_KEY": "image-key",
            "MORETALE_OUTPUTS_DIR": self.tmp_dir.name,
            "MORETALE_HEALTHCHECK_TIMEOUT_SEC": "1",
            "MORETALE_STORY_PAGE_COUNT": "3",
            "MORETALE_ALLOWED_STORY_MODELS": "gemini-2.5-flash",
            "MORETALE_ALLOWED_TTS_MODELS": "gemini-2.5-flash-preview-tts",
            "MORETALE_ALLOWED_ILLUSTRATION_MODELS": "gemini-2.5-flash-image",
        }

    def _run(self, env: dict[str, str]):
        with patch.dict(os.environ, env, clear=False):
            return run_health_checks(get_settings())

    def test_health_returns_ok_when_required_dependencies_pass(self) -> None:
        with patch("app.services.health._lookup_genai_model") as lookup:
            status_code, payload = self._run(self.base_env)

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"]["apiAuth"]["status"], "ok")
        self.assertEqual(payload["checks"]["outputsDir"]["status"], "ok")
        self.assertEqual(payload["checks"]["storage"]["status"], "ok")
        self.assertEqual(payload["checks"]["geminiStory"]["model"], "gemini-2.5-flash")
        self.assertEqual(lookup.call_count, 3)

    def test_health_returns_503_when_moretale_api_key_missing(self) -> None:
        env = {**self.base_env, "MORETALE_API_KEY": ""}
        with patch("app.services.health._lookup_genai_model"):
            status_code, payload = self._run(env)

        self.assertEqual(status_code, 503)
        self.assertEqual(payload["status"], "unhealthy")
        self.assertEqual(payload["checks"]["apiAuth"]["error"]["type"], "missing_env")

    def test_health_returns_503_when_story_key_missing(self) -> None:
        env = {**self.base_env, "GEMINI_STORY_API_KEY": ""}
        with patch("app.services.health._lookup_genai_model"):
            status_code, payload = self._run(env)

        self.assertEqual(status_code, 503)
        self.assertEqual(payload["checks"]["geminiStory"]["error"]["type"], "missing_env")

    def test_health_returns_503_when_tts_key_missing(self) -> None:
        env = {**self.base_env, "GEMINI_TTS_API_KEY": ""}
        with patch("app.services.health._lookup_genai_model"):
            status_code, payload = self._run(env)

        self.assertEqual(status_code, 503)
        self.assertEqual(payload["checks"]["geminiTts"]["error"]["type"], "missing_env")

    def test_health_returns_503_when_illustration_key_missing(self) -> None:
        env = {**self.base_env, "NANO_BANANA_KEY": ""}
        with patch("app.services.health._lookup_genai_model"):
            status_code, payload = self._run(env)

        self.assertEqual(status_code, 503)
        self.assertEqual(payload["checks"]["illustration"]["error"]["type"], "missing_env")

    def test_health_returns_503_when_outputs_dir_write_fails(self) -> None:
        blocker = Path(self.tmp_dir.name) / "not-a-directory"
        blocker.write_text("blocked", encoding="utf-8")
        env = {**self.base_env, "MORETALE_OUTPUTS_DIR": str(blocker)}
        with patch("app.services.health._lookup_genai_model"):
            status_code, payload = self._run(env)

        self.assertEqual(status_code, 503)
        self.assertEqual(payload["checks"]["outputsDir"]["status"], "failed")

    def test_health_returns_503_when_gcs_bucket_missing(self) -> None:
        env = {
            **self.base_env,
            "MORETALE_STORAGE_BACKEND": "gcs",
            "MORETALE_GCS_BUCKET": "",
        }
        with patch("app.services.health._lookup_genai_model"):
            status_code, payload = self._run(env)

        self.assertEqual(status_code, 503)
        self.assertEqual(payload["checks"]["storage"]["error"]["type"], "missing_env")

    def test_health_checks_gcs_storage_when_enabled(self) -> None:
        env = {
            **self.base_env,
            "MORETALE_STORAGE_BACKEND": "gcs",
            "MORETALE_GCS_BUCKET": "moretale-assets",
        }
        with patch("app.services.health._lookup_genai_model"), patch(
            "app.services.storage_backend._build_gcs_client",
        ) as client_factory:
            status_code, payload = self._run(env)

        bucket = client_factory.return_value.bucket.return_value
        self.assertEqual(status_code, 200)
        self.assertEqual(payload["checks"]["storage"]["status"], "ok")
        self.assertEqual(payload["checks"]["storage"]["backend"], "gcs")
        self.assertEqual(bucket.blob.return_value.upload_from_filename.call_count, 1)
        self.assertEqual(bucket.blob.return_value.delete.call_count, 1)

    def test_health_returns_503_when_gemini_lookup_fails(self) -> None:
        with patch(
            "app.services.health._lookup_genai_model",
            side_effect=RuntimeError("model unavailable"),
        ):
            status_code, payload = self._run(self.base_env)

        self.assertEqual(status_code, 503)
        self.assertEqual(payload["checks"]["geminiStory"]["error"]["type"], "RuntimeError")

    def test_health_returns_503_when_gemini_lookup_times_out(self) -> None:
        with patch(
            "app.services.health._run_with_timeout",
            side_effect=HealthCheckError("timeout", "dependency check exceeded 1s timeout"),
        ):
            status_code, payload = self._run(self.base_env)

        self.assertEqual(status_code, 503)
        self.assertEqual(payload["checks"]["geminiStory"]["error"]["type"], "timeout")


if __name__ == "__main__":
    unittest.main()
