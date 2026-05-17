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
        FakeTTSGenerator.prompts = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = {
                "MORETALE_OUTPUTS_DIR": tmp_dir,
                "GEMINI_TTS_API_KEY": "test-tts-key",
            }
            with patch.dict(os.environ, env, clear=False), patch(
                "generators.tts.tts_generator.TTSGenerator",
                FakeTTSGenerator,
            ):
                result = run_tts_job(
                    job_id="job-1",
                    request_payload={
                        "callbackUrl": "https://backend.test/internal/ai/callback",
                        "text": "hello",
                        "language": "KO-kr",
                        "style": "neutral",
                    },
                )

        self.assertEqual(result["language"], "ko-KR")
        self.assertEqual(result["duration"], 2)
        self.assertIn("/static/outputs/job-1/tts/tts_001.wav", result["audioUrl"])
        self.assertEqual(len(FakeTTSGenerator.prompts), 1)
        self.assertIn("Voice style: neutral.", FakeTTSGenerator.prompts[0])


if __name__ == "__main__":
    unittest.main()
