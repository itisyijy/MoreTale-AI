import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    from generators.illustration.illustration_generator import (
        IllustrationGenerator,
        _resolve_api_key,
    )
    from generators.illustration.illustration_cover_prompt import build_cover_prompt
except ModuleNotFoundError:  # pragma: no cover
    IllustrationGenerator = None
    _resolve_api_key = None
    build_cover_prompt = None


if IllustrationGenerator is not None:
    class _FakeIllustrationGenerator(IllustrationGenerator):
        def __init__(self):
            super().__init__(api_key="dummy", client=SimpleNamespace(models=None))
            self.seen_requests: list[tuple[str, str | None]] = []

        def _generate_image_bytes(
            self,
            prompt: str,
            *,
            aspect_ratio: str | None = None,
        ) -> tuple[bytes, str]:
            self.seen_requests.append((prompt, aspect_ratio))
            return b"fake-image-bytes", "image/png"
else:  # pragma: no cover
    _FakeIllustrationGenerator = None


@unittest.skipIf(
    IllustrationGenerator is None or _resolve_api_key is None or build_cover_prompt is None,
    "illustration dependencies are not installed in this environment",
)
class TestIllustrationPromptBuild(unittest.TestCase):
    def test_resolve_api_key_uses_nano_banana_key(self):
        with patch.dict(os.environ, {"NANO_BANANA_KEY": "banana-key"}, clear=True):
            self.assertEqual(_resolve_api_key(), "banana-key")

    def test_resolve_api_key_raises_without_nano_banana_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError) as context:
                _resolve_api_key()
        self.assertIn("NANO_BANANA_KEY environment variable not set.", str(context.exception))

    def test_build_page_prompt_uses_scene_and_full_prompt(self):
        story = SimpleNamespace(
            illustration_prefix="Dreamy style, Main character",
            image_style="Dreamy style",
            main_character_design="Main character",
        )
        page = SimpleNamespace(
            page_number=1,
            illustration_prompt="Dreamy style, Main character, full prompt details",
            illustration_scene_prompt="page specific scene",
        )

        prompt, mode = IllustrationGenerator._build_page_prompt(story=story, page=page)

        self.assertEqual(mode, "scene_plus_full")
        self.assertIn("Dreamy style, Main character, page specific scene", prompt)
        self.assertIn("Reference details for consistency", prompt)
        self.assertIn("full prompt details", prompt)

    def test_build_page_prompt_falls_back_to_full_prompt(self):
        story = SimpleNamespace(
            illustration_prefix="",
            image_style="Dreamy style",
            main_character_design="Main character",
        )
        page = SimpleNamespace(
            page_number=2,
            illustration_prompt="fallback full prompt",
            illustration_scene_prompt="",
        )

        prompt, mode = IllustrationGenerator._build_page_prompt(story=story, page=page)

        self.assertEqual(mode, "full_only")
        self.assertIn("CHARACTER CONSISTENCY LOCK", prompt)
        self.assertIn("Fixed character design: Main character", prompt)
        self.assertIn("fallback full prompt", prompt)

    def test_build_page_prompt_avoids_double_prefix_when_scene_equals_full_prompt(self):
        story = SimpleNamespace(
            illustration_prefix="Dreamy style, Main character",
            image_style="Dreamy style",
            main_character_design="Main character",
        )
        full_prompt = "Different character with a fully custom prompt"
        page = SimpleNamespace(
            page_number=3,
            illustration_prompt=full_prompt,
            illustration_scene_prompt=full_prompt,
        )

        prompt, mode = IllustrationGenerator._build_page_prompt(story=story, page=page)

        self.assertEqual(mode, "full_only")
        self.assertIn("CHARACTER CONSISTENCY LOCK", prompt)
        self.assertIn(full_prompt, prompt)

    def test_build_page_prompt_uses_character_bible_lock(self):
        from generators.character.character_model import CharacterBible

        story = SimpleNamespace(
            illustration_prefix="Dreamy style, Main character",
            image_style="Dreamy style",
            main_character_design="loose design",
        )
        page = SimpleNamespace(
            page_number=4,
            illustration_prompt="Dreamy style, Main character, full prompt details",
            illustration_scene_prompt="page specific scene",
        )
        bible = CharacterBible(
            fixed_design="fixed bible design",
            art_consistency_prompt="CHARACTER CONSISTENCY LOCK: fixed bible design",
        )

        prompt, mode = IllustrationGenerator._build_page_prompt(
            story=story,
            page=page,
            character_bible=bible,
        )

        self.assertEqual(mode, "scene_plus_full")
        self.assertIn("CHARACTER CONSISTENCY LOCK: fixed bible design", prompt)
        self.assertNotIn("Fixed character design: loose design", prompt)

    def test_build_cover_prompt_forbids_visible_title_text(self):
        story = SimpleNamespace(
            title_primary="별빛 숲의 노래",
            title_secondary="Song of the Starlit Forest",
            illustration_prefix="Dreamy watercolor, Main character",
            image_style="Dreamy watercolor",
            main_character_design="Main character",
            pages=[
                SimpleNamespace(
                    illustration_prompt="full prompt 1",
                    illustration_scene_prompt="A lantern glows beside a quiet forest path.",
                ),
                SimpleNamespace(
                    illustration_prompt="full prompt 2",
                    illustration_scene_prompt="The child looks up at floating lights over a lake.",
                ),
                SimpleNamespace(
                    illustration_prompt="full prompt 3",
                    illustration_scene_prompt="Friends gather under a bright moon near tall trees.",
                ),
            ],
        )

        prompt = build_cover_prompt(story)

        self.assertNotIn("별빛 숲의 노래", prompt)
        self.assertNotIn("Song of the Starlit Forest", prompt)
        self.assertIn("Do not render any visible text", prompt)
        self.assertIn("Hangul", prompt)


@unittest.skipIf(
    IllustrationGenerator is None or _FakeIllustrationGenerator is None,
    "illustration dependencies are not installed in this environment",
)
class TestIllustrationGenerationPipeline(unittest.TestCase):
    def test_generate_from_story_creates_page_images_cover_and_manifest(self):
        generator = _FakeIllustrationGenerator()
        story = SimpleNamespace(
            pages=[
                SimpleNamespace(
                    page_number=1,
                    illustration_prompt="full prompt 1",
                    illustration_scene_prompt="scene 1",
                ),
                SimpleNamespace(
                    page_number=2,
                    illustration_prompt="full prompt 2",
                    illustration_scene_prompt="scene 2",
                ),
            ],
            illustration_prefix="prefix",
            cover_illustration_prompt="storybook cover prompt",
            image_style="style",
            main_character_design="design",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = generator.generate_from_story(
                story=story,
                output_dir=tmp_dir,
                skip_existing=False,
            )

            self.assertEqual(result["total_tasks"], 3)
            self.assertEqual(result["generated"], 3)
            self.assertEqual(result["failed"], 0)
            self.assertTrue(
                os.path.exists(os.path.join(tmp_dir, "illustrations", "page_01.png"))
            )
            self.assertTrue(
                os.path.exists(os.path.join(tmp_dir, "illustrations", "page_02.png"))
            )
            self.assertTrue(
                os.path.exists(os.path.join(tmp_dir, "illustrations", "cover.png"))
            )
            self.assertTrue(
                os.path.exists(os.path.join(tmp_dir, "illustrations", "manifest.json"))
            )
            self.assertEqual(result["cover"]["status"], "generated")
            self.assertEqual(len(generator.seen_requests), 3)
            self.assertIn("CHARACTER CONSISTENCY LOCK", generator.seen_requests[0][0])
            self.assertIn("CHARACTER CONSISTENCY LOCK", generator.seen_requests[2][0])
            self.assertEqual(generator.seen_requests[0][1], None)
            self.assertEqual(generator.seen_requests[1][1], None)
            self.assertEqual(generator.seen_requests[2][1], "5:4")

    def test_generate_from_story_skips_existing_page_and_cover(self):
        generator = _FakeIllustrationGenerator()
        story = SimpleNamespace(
            pages=[
                SimpleNamespace(
                    page_number=1,
                    illustration_prompt="full prompt 1",
                    illustration_scene_prompt="scene 1",
                )
            ],
            illustration_prefix="prefix",
            cover_illustration_prompt="storybook cover prompt",
            image_style="style",
            main_character_design="design",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            illustrations_dir = os.path.join(tmp_dir, "illustrations")
            os.makedirs(illustrations_dir, exist_ok=True)
            existing_path = os.path.join(illustrations_dir, "page_01.png")
            with open(existing_path, "wb") as file:
                file.write(b"existing")
            existing_cover_path = os.path.join(illustrations_dir, "cover.png")
            with open(existing_cover_path, "wb") as file:
                file.write(b"existing cover")

            result = generator.generate_from_story(
                story=story,
                output_dir=tmp_dir,
                skip_existing=True,
            )

            self.assertEqual(result["generated"], 0)
            self.assertEqual(result["skipped"], 2)
            self.assertEqual(result["cover"]["status"], "skipped_exists")
            self.assertEqual(len(generator.seen_requests), 0)


if __name__ == "__main__":
    unittest.main()
