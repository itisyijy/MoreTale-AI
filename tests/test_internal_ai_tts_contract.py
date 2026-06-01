import io
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from app.services.internal_ai_jobs import run_tts_job


def _wav_bytes(duration_seconds: int = 2, sample_rate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * sample_rate * duration_seconds)
    return buffer.getvalue()


class FakeTTSGenerator:
    prompts: list[str] = []

    def __init__(self, **_kwargs):
        pass

    def _build_prompt(self, language_name: str, text: str) -> str:
        return f"Read in natural {language_name} children's storytelling tone.\n{text}"

    def _build_contents(self, prompt: str) -> list[str]:
        self.__class__.prompts.append(prompt)
        return [prompt]

    def _build_config(self) -> object:
        return object()

    def _stream_audio_bytes(self, **_kwargs) -> tuple[bytes, str]:
        return _wav_bytes(duration_seconds=2), "audio/wav"

    def _save_audio_file(self, file_path: str, audio_bytes: bytes, _mime_type: str) -> None:
        Path(file_path).write_bytes(audio_bytes)


class TestInternalAITTSContract(unittest.TestCase):
    def test_tts_job_accepts_backend_style_and_returns_duration(self) -> None:
        for index, language_input in enumerate(("KO-kr", "ko-KR"), start=1):
            with self.subTest(language_input=language_input):
                FakeTTSGenerator.prompts = []
                with tempfile.TemporaryDirectory() as tmp_dir:
                    env = {
                        "MORETALE_OUTPUTS_DIR": tmp_dir,
                        "MORETALE_STORY_PAGE_COUNT": "3",
                        "GEMINI_TTS_API_KEY": "test-tts-key",
                    }
                    with patch.dict(os.environ, env, clear=False), patch(
                        "generators.tts.tts_generator.TTSGenerator",
                        FakeTTSGenerator,
                    ):
                        result = run_tts_job(
                            job_id=f"job-{index}",
                            request_payload={
                                "callbackUrl": "https://backend.test/internal/ai/callback",
                                "text": "hello",
                                "language": language_input,
                                "style": "neutral",
                            },
                        )

                self.assertEqual(result["language"], "ko-KR")
                self.assertEqual(result["duration"], 2)
                self.assertIn(f"/static/outputs/job-{index}/tts/tts_001.wav", result["audioUrl"])
                self.assertEqual(len(FakeTTSGenerator.prompts), 1)
                self.assertIn("Voice style: neutral.", FakeTTSGenerator.prompts[0])

    def test_tts_job_uploads_audio_to_gcs_when_enabled(self) -> None:
        from app.services.internal_ai_runners import run_tts_job

        with tempfile.TemporaryDirectory() as tmp_dir:
            env = {
                "GEMINI_TTS_API_KEY": "dummy",
                "MORETALE_OUTPUTS_DIR": tmp_dir,
                "MORETALE_STORY_PAGE_COUNT": "3",
                "MORETALE_STORAGE_BACKEND": "gcs",
                "MORETALE_GCS_BUCKET": "moretale-assets",
                "MORETALE_GCS_KEY_PREFIX": "generated",
            }
            with patch.dict(os.environ, env, clear=False), patch(
                "generators.tts.tts_generator.TTSGenerator",
                FakeTTSGenerator,
            ), patch("app.services.storage_backend._build_gcs_client") as client_factory:
                result = run_tts_job(
                    job_id="job-1",
                    request_payload={
                        "callbackUrl": "https://backend.test/internal/ai/callback",
                        "text": "hello",
                        "language": "ko-KR",
                    },
                )

        bucket = client_factory.return_value.bucket.return_value
        bucket.blob.assert_called_once_with("generated/job-1/tts/tts_001.wav")
        self.assertEqual(
            result["audioUrl"],
            "https://storage.googleapis.com/moretale-assets/generated/job-1/tts/tts_001.wav",
        )


if __name__ == "__main__":
    unittest.main()
