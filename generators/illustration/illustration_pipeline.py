from pathlib import Path
from typing import Any

from google import genai

from generators.character.character_model import CharacterBible
from generators.story.story_model import Story

from .illustration_cover_prompt import build_cover_prompt
from .illustration_env import resolve_api_key
from .illustration_image_client import ImageGenerationClient
from .illustration_prompt_builder import (
    build_character_consistency_lock,
    build_page_prompt,
)
from .illustration_storage import (
    find_existing_cover_asset,
    find_existing_page_asset,
    pick_image_extension,
    write_manifest,
)


class IllustrationGenerator:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash-image",
        aspect_ratio: str = "1:1",
        cover_aspect_ratio: str = "5:4",
        request_interval_sec: float = 1.0,
        client: genai.Client | None = None,
    ):
        self.client = client or genai.Client(api_key=api_key or resolve_api_key())
        self.model_name = model_name
        self.aspect_ratio = aspect_ratio
        self.cover_aspect_ratio = cover_aspect_ratio
        self.request_interval_sec = max(0.0, request_interval_sec)
        self.image_client = ImageGenerationClient(
            client=self.client,
            model_name=self.model_name,
            aspect_ratio=self.aspect_ratio,
            request_interval_sec=self.request_interval_sec,
        )

    @staticmethod
    def load_story(story_json_path: str) -> Story:
        with open(story_json_path, "r", encoding="utf-8") as file:
            return Story.model_validate_json(file.read())

    @staticmethod
    def _build_page_prompt(
        story: Story,
        page,
        character_bible: CharacterBible | None = None,
    ) -> tuple[str, str]:
        return build_page_prompt(
            story=story,
            page=page,
            character_bible=character_bible,
        )

    @staticmethod
    def _build_cover_prompt(
        story: Story,
        character_bible: CharacterBible | None = None,
    ) -> str:
        prompt = (story.cover_illustration_prompt or "").strip()
        if prompt:
            cover_prompt = prompt
        else:
            cover_prompt = build_cover_prompt(story)

        character_lock = build_character_consistency_lock(
            story=story,
            character_bible=character_bible,
        )
        if character_lock and character_lock not in cover_prompt:
            return f"{character_lock}\n\n{cover_prompt}"
        return cover_prompt

    def _generate_image_bytes(
        self,
        prompt: str,
        *,
        aspect_ratio: str | None = None,
    ) -> tuple[bytes, str]:
        target_aspect_ratio = (aspect_ratio or self.aspect_ratio).strip() or self.aspect_ratio
        original_aspect_ratio = self.image_client.aspect_ratio
        self.image_client.aspect_ratio = target_aspect_ratio
        try:
            return self.image_client.generate_image_bytes(prompt=prompt)
        finally:
            self.image_client.aspect_ratio = original_aspect_ratio

    def generate_from_story(
        self,
        story: Story,
        output_dir: str,
        skip_existing: bool = True,
        generate_cover: bool = True,
        character_bible: CharacterBible | None = None,
    ) -> dict[str, Any]:
        illustration_dir = Path(output_dir) / "illustrations"
        illustration_dir.mkdir(parents=True, exist_ok=True)

        page_generated = 0
        page_skipped = 0
        page_failed = 0
        entries: list[dict[str, Any]] = []

        for page in story.pages:
            page_number = page.page_number
            if skip_existing:
                existing_path = find_existing_page_asset(
                    illustration_dir=illustration_dir,
                    page_number=page_number,
                )
                if existing_path:
                    page_skipped += 1
                    print(f"SKIP page={page_number} reason=exists path={existing_path}")
                    entries.append(
                        {
                            "asset_type": "page",
                            "page_number": page_number,
                            "status": "skipped_exists",
                            "path": existing_path,
                            "aspect_ratio": self.aspect_ratio,
                        }
                    )
                    continue

            try:
                prompt, prompt_mode = self._build_page_prompt(
                    story=story,
                    page=page,
                    character_bible=character_bible,
                )
                image_bytes, mime_type = self._generate_image_bytes(prompt=prompt)
                extension = pick_image_extension(mime_type)
                image_path = illustration_dir / f"page_{page_number:02d}{extension}"

                with open(image_path, "wb") as file:
                    file.write(image_bytes)

                page_generated += 1
                print(f"OK page={page_number} path={image_path} mode={prompt_mode}")
                entries.append(
                    {
                        "asset_type": "page",
                        "page_number": page_number,
                        "status": "generated",
                        "path": str(image_path),
                        "prompt_mode": prompt_mode,
                        "aspect_ratio": self.aspect_ratio,
                    }
                )
            except Exception as error:
                page_failed += 1
                print(f"FAIL page={page_number} error={error}")
                entries.append(
                    {
                        "asset_type": "page",
                        "page_number": page_number,
                        "status": "failed",
                        "error": str(error),
                        "aspect_ratio": self.aspect_ratio,
                    }
                )

        cover_status = "not_requested"
        cover_error: str | None = None
        cover_path: str | None = None
        cover_generated = 0
        cover_skipped = 0
        cover_failed = 0

        if generate_cover:
            if skip_existing:
                existing_cover_path = find_existing_cover_asset(illustration_dir=illustration_dir)
                if existing_cover_path:
                    cover_status = "skipped_exists"
                    cover_path = existing_cover_path
                    cover_skipped = 1
                    print(f"SKIP cover reason=exists path={existing_cover_path}")
                    entries.append(
                        {
                            "asset_type": "cover",
                            "status": cover_status,
                            "path": existing_cover_path,
                            "prompt_mode": "cover_prompt",
                            "aspect_ratio": self.cover_aspect_ratio,
                        }
                    )

            if cover_status == "not_requested":
                try:
                    prompt = self._build_cover_prompt(
                        story=story,
                        character_bible=character_bible,
                    )
                    image_bytes, mime_type = self._generate_image_bytes(
                        prompt=prompt,
                        aspect_ratio=self.cover_aspect_ratio,
                    )
                    extension = pick_image_extension(mime_type)
                    image_path = illustration_dir / f"cover{extension}"

                    with open(image_path, "wb") as file:
                        file.write(image_bytes)

                    cover_status = "generated"
                    cover_path = str(image_path)
                    cover_generated = 1
                    print(f"OK cover path={image_path} mode=cover_prompt")
                    entries.append(
                        {
                            "asset_type": "cover",
                            "status": cover_status,
                            "path": cover_path,
                            "prompt_mode": "cover_prompt",
                            "aspect_ratio": self.cover_aspect_ratio,
                        }
                    )
                except Exception as error:
                    cover_status = "failed"
                    cover_error = str(error)
                    cover_failed = 1
                    print(f"FAIL cover error={error}")
                    entries.append(
                        {
                            "asset_type": "cover",
                            "status": cover_status,
                            "error": cover_error,
                            "prompt_mode": "cover_prompt",
                            "aspect_ratio": self.cover_aspect_ratio,
                        }
                    )

        manifest_path = illustration_dir / "manifest.json"
        total_tasks = len(story.pages) + (1 if generate_cover else 0)
        total_generated = page_generated + cover_generated
        total_skipped = page_skipped + cover_skipped
        total_failed = page_failed + cover_failed
        write_manifest(
            manifest_path=manifest_path,
            model_name=self.model_name,
            aspect_ratio=self.aspect_ratio,
            cover_aspect_ratio=self.cover_aspect_ratio if generate_cover else None,
            total_tasks=total_tasks,
            generated=total_generated,
            skipped=total_skipped,
            failed=total_failed,
            entries=entries,
        )

        return {
            "total_tasks": total_tasks,
            "generated": total_generated,
            "skipped": total_skipped,
            "failed": total_failed,
            "page_total_tasks": len(story.pages),
            "page_generated": page_generated,
            "page_skipped": page_skipped,
            "page_failed": page_failed,
            "cover": {
                "enabled": generate_cover,
                "status": cover_status,
                "error": cover_error,
                "path": cover_path,
                "aspect_ratio": self.cover_aspect_ratio,
            },
            "manifest_path": str(manifest_path),
        }
