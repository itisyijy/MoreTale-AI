import subprocess
import sys
import unittest
import os
from importlib import import_module

from generators.illustration.illustration_prompt_utils import (
    build_illustration_prefix as canonical_build_illustration_prefix,
    split_scene_prompt as canonical_split_scene_prompt,
)
from generators.story.story_prompts import StoryPrompt as canonical_story_prompt_class


class TestImportCompatibility(unittest.TestCase):
    def test_canonical_story_prompt_import(self):
        module = import_module("generators.story.story_prompts")
        self.assertIs(module.StoryPrompt, canonical_story_prompt_class)

    def test_canonical_illustration_utils_import(self):
        module = import_module("generators.illustration.illustration_prompt_utils")
        self.assertIs(module.build_illustration_prefix, canonical_build_illustration_prefix)
        self.assertIs(module.split_scene_prompt, canonical_split_scene_prompt)

    def test_legacy_prompt_module_imports_removed(self):
        with self.assertRaises(ModuleNotFoundError):
            import_module("prompts.story_prompts")
        with self.assertRaises(ModuleNotFoundError):
            import_module("prompts.illustration_prompt_utils")

    def test_app_import_does_not_load_google_genai(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; import app.main; "
                    "raise SystemExit(1 if 'google.genai' in sys.modules else 0)"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "MORETALE_STORY_PAGE_COUNT": "3"},
        )
        if (
            result.returncode != 0
            and "ModuleNotFoundError: No module named 'fastapi'" in result.stderr
        ):
            self.skipTest("fastapi dependency is not installed in this environment")
        self.assertEqual(result.returncode, 0)

    def test_result_builder_import_does_not_load_generators(self):
        code = (
            "import sys; import app.services.story_result_builder; "
            "blocked = {"
            "'google.genai', "
            "'generators.story.story_generator', "
            "'generators.quiz.quiz_generator', "
            "'generators.tts.tts_generator', "
            "'generators.illustration.illustration_pipeline'"
            "}; "
            "raise SystemExit(1 if blocked.intersection(sys.modules) else 0)"
        )
        result = subprocess.run([sys.executable, "-c", code], check=False)
        self.assertEqual(result.returncode, 0)

    def test_lazy_generator_import_compatibility(self):
        from generators.illustration import IllustrationGenerator
        from generators.quiz import QuizGenerator
        from generators.story import StoryGenerator
        from generators.tts import TTSGenerator

        self.assertEqual(StoryGenerator.__name__, "StoryGenerator")
        self.assertEqual(QuizGenerator.__name__, "QuizGenerator")
        self.assertEqual(TTSGenerator.__name__, "TTSGenerator")
        self.assertEqual(IllustrationGenerator.__name__, "IllustrationGenerator")


if __name__ == "__main__":
    unittest.main()
