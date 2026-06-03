from generators.story.story_model import Story
from generators.character.character_model import CharacterBible

from .illustration_prompt_utils import build_illustration_prefix


def build_character_consistency_lock(
    story: Story,
    character_bible: CharacterBible | None = None,
) -> str:
    if character_bible is not None and character_bible.art_consistency_prompt.strip():
        return character_bible.art_consistency_prompt.strip()

    design = (getattr(story, "main_character_design", "") or "").strip()
    if not design:
        return ""

    return (
        "CHARACTER CONSISTENCY LOCK: Use the exact same protagonist design in every "
        "illustration. Do not change hairstyle, face shape, eye shape, outfit, age, "
        "ethnicity, or body proportions. Only change pose, expression, camera angle, "
        f"and scene action. Fixed character design: {design}"
    )


def _with_character_lock(prompt: str, character_lock: str) -> str:
    prompt = (prompt or "").strip()
    character_lock = (character_lock or "").strip()
    if not character_lock:
        return prompt
    if character_lock in prompt:
        return prompt
    return f"{character_lock}\n\n{prompt}" if prompt else character_lock


def build_page_prompt(
    story: Story,
    page,
    character_bible: CharacterBible | None = None,
) -> tuple[str, str]:
    illustration_prefix = (
        (story.illustration_prefix or "").strip()
        or build_illustration_prefix(story.image_style, story.main_character_design)
    )
    full_prompt = (page.illustration_prompt or "").strip()
    scene_prompt = (page.illustration_scene_prompt or "").strip()
    character_lock = build_character_consistency_lock(
        story=story,
        character_bible=character_bible,
    )

    # When scene extraction falls back to the full prompt text, reuse the full
    # prompt directly instead of prepending the shared prefix again.
    if scene_prompt and full_prompt and scene_prompt == full_prompt:
        return _with_character_lock(full_prompt, character_lock), "full_only"

    if scene_prompt:
        scene_focused_prompt = ", ".join(
            part for part in (illustration_prefix, scene_prompt) if part
        )
        if full_prompt:
            combined_prompt = (
                f"{scene_focused_prompt}\n\n"
                f"Reference details for consistency: {full_prompt}"
            )
        else:
            combined_prompt = scene_focused_prompt
        return _with_character_lock(combined_prompt, character_lock), "scene_plus_full"

    if full_prompt:
        return _with_character_lock(full_prompt, character_lock), "full_only"

    if illustration_prefix:
        return _with_character_lock(illustration_prefix, character_lock), "prefix_only"

    raise ValueError(f"page={page.page_number} has no illustration prompt text.")
