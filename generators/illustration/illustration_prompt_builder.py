from generators.story.story_model import Story

from .illustration_prompt_utils import build_illustration_prefix


def build_page_prompt(story: Story, page) -> tuple[str, str]:
    illustration_prefix = (
        (story.illustration_prefix or "").strip()
        or build_illustration_prefix(story.image_style, story.main_character_design)
    )
    full_prompt = (page.illustration_prompt or "").strip()
    scene_prompt = (page.illustration_scene_prompt or "").strip()

    # When scene extraction falls back to the full prompt text, reuse the full
    # prompt directly instead of prepending the shared prefix again.
    if scene_prompt and full_prompt and scene_prompt == full_prompt:
        return full_prompt, "full_only"

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
        return combined_prompt, "scene_plus_full"

    if full_prompt:
        return full_prompt, "full_only"

    if illustration_prefix:
        return illustration_prefix, "prefix_only"

    raise ValueError(f"page={page.page_number} has no illustration prompt text.")
