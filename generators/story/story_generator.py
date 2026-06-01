import os
import re
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv

from generators.illustration.illustration_cover_prompt import build_cover_prompt
from generators.illustration.illustration_prompt_utils import (
    build_illustration_prefix,
    split_scene_prompt,
)
from generators.story.story_model import GeneratedStory, Story
from generators.story.story_prompts import StoryPrompt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _slugify_identifier(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


class StoryGenerator:
    def __init__(self, model_name: str = "gemini-2.5-flash", include_style_guide: bool = True):
        gemini_api_key = (os.getenv("GEMINI_STORY_API_KEY") or "").strip()
        if not gemini_api_key:
            raise ValueError("GEMINI_STORY_API_KEY environment variable not set.")
        self.client = genai.Client(api_key=gemini_api_key)
        self.model_name = model_name
        # `include_style_guide` is kept for backwards compatibility. The style guide
        # is now always appended to the system instruction.
        _ = include_style_guide
        self.prompts = StoryPrompt()

    def generate_story(
        self,
        child_name: str,
        primary_lang: str,
        secondary_lang: str,
        theme: str,
        extra_prompt: str = "",
        child_age: Optional[int] = None,
        primary_proficiency: str = "native",
        secondary_proficiency: str = "beginner",
        cultures: str = "",
        foreign_terms: str = "",
        style_preset: str = "vibrant_storybook",
        page_count: int | None = None,
        tone_hint: str = "",
        gender: Optional[str] = None,
        family_situation: Optional[str] = None,
        interest: Optional[str] = None,
    ) -> Story:
        if page_count is None:
            from app.core.config import get_settings

            page_count = get_settings().story_page_count

        user_prompt = self.prompts.generate_user_prompt(
            child_name=child_name,
            child_age=child_age,
            primary_lang=primary_lang,
            secondary_lang=secondary_lang,
            theme=theme,
            extra_prompt=extra_prompt,
            primary_proficiency=primary_proficiency,
            secondary_proficiency=secondary_proficiency,
            cultures=cultures,
            foreign_terms=foreign_terms,
            style_preset=style_preset,
            page_count=page_count,
            tone_hint=tone_hint,
            gender=gender,
            family_situation=family_situation,
            interest=interest,
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.prompts.system_instruction,
                    temperature=1.0, # High creativity
                    response_mime_type="application/json",
                    response_schema=GeneratedStory,
                ),
            )
            
            if response.parsed:
                story = Story.model_validate(response.parsed.model_dump())
            else:
                story = Story.model_validate_json(response.text)

            self._populate_illustration_fields(story)
            self._populate_vocabulary_fields(story)
            return story

        except Exception as e:
            print(f"Error generating story: {e}")
            raise

    @staticmethod
    def _populate_illustration_fields(story: Story) -> None:
        illustration_prefix = build_illustration_prefix(
            story.image_style, story.main_character_design
        )
        story.illustration_prefix = illustration_prefix

        for page in story.pages:
            scene, method = split_scene_prompt(
                illustration_prefix=illustration_prefix,
                main_character_design=story.main_character_design,
                full_prompt=page.illustration_prompt,
            )
            page.illustration_scene_prompt = scene

            if method == "fallback":
                print(
                    "[warn] Could not split illustration_prompt into scene prompt; "
                    f"page={page.page_number} method={method}"
                )

        story.cover_illustration_prompt = build_cover_prompt(story)

    @staticmethod
    def _populate_vocabulary_fields(story: Story) -> None:
        for page in story.pages:
            seen_ids: set[str] = set()
            for index, entry in enumerate(page.vocabulary, start=1):
                raw_id = (
                    entry.entry_id
                    or _slugify_identifier(entry.primary_word)
                    or _slugify_identifier(entry.secondary_word)
                    or f"word-{index:02d}"
                )
                candidate = raw_id
                suffix = 2
                while candidate in seen_ids:
                    candidate = f"{raw_id}-{suffix}"
                    suffix += 1
                entry.entry_id = candidate
                seen_ids.add(candidate)
