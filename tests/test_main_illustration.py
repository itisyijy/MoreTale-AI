import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    import main
except ModuleNotFoundError:  # pragma: no cover
    main = None


def _fake_pipeline_result(illustration_result: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        story=SimpleNamespace(title_primary="Test Story"),
        story_json_path=Path("outputs/story_gemini-2.5-flash.json"),
        tts_result=None,
        illustration_result=illustration_result,
    )


@unittest.skipIf(
    main is None,
    "CLI dependencies are not installed in this environment",
)
class TestMainIllustration(unittest.TestCase):
    def test_enable_illustration_requires_api_key(self):
        args = [
            "main.py",
            "--child_name",
            "Mina",
            "--primary_lang",
            "Korean",
            "--secondary_lang",
            "English",
            "--enable_illustration",
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                with patch(
                    "main.run_story_generation_pipeline",
                    side_effect=RuntimeError("NANO_BANANA_KEY environment variable not set."),
                ):
                    with patch.object(sys, "argv", args):
                        with self.assertRaises(SystemExit) as context:
                            main.main()
                self.assertEqual(context.exception.code, 1)
            finally:
                os.chdir(original_cwd)

    def test_enable_illustration_uses_defaults(self):
        args = [
            "main.py",
            "--child_name",
            "Mina",
            "--primary_lang",
            "Spanish",
            "--secondary_lang",
            "French",
            "--enable_illustration",
        ]

        illustration_result = {
            "total_tasks": 33,
            "generated": 33,
            "skipped": 0,
            "failed": 0,
            "cover": {
                "enabled": True,
                "status": "generated",
                "error": None,
                "path": "outputs/illustrations/cover.png",
                "aspect_ratio": "5:4",
            },
            "manifest_path": "outputs/illustrations/manifest.json",
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                with patch("main.datetime.datetime") as mocked_datetime:
                    mocked_datetime.now.return_value.strftime.return_value = "20260211_000000"
                    with patch(
                        "main.run_story_generation_pipeline",
                        return_value=_fake_pipeline_result(
                            illustration_result=illustration_result
                        ),
                    ) as mocked_pipeline:
                        with patch.object(sys, "argv", args):
                            main.main()

                pipeline_request = mocked_pipeline.call_args.kwargs["request"]
                self.assertTrue(pipeline_request.enable_illustration)
                self.assertTrue(pipeline_request.enable_cover_illustration)
                self.assertEqual(pipeline_request.illustration_model, "gemini-2.5-flash-image")
                self.assertEqual(pipeline_request.illustration_aspect_ratio, "1:1")
                self.assertEqual(
                    pipeline_request.illustration_cover_aspect_ratio,
                    "5:4",
                )
                self.assertEqual(pipeline_request.illustration_request_interval_sec, 1.0)
                self.assertFalse(pipeline_request.illustration_skip_existing)
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
