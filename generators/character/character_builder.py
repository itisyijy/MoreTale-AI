from __future__ import annotations

import re
from typing import TYPE_CHECKING

from generators.character.character_model import CharacterBible

if TYPE_CHECKING:
    from app.services.generation_pipeline import StoryPipelineRequest


_FALLBACK_OUTFITS = {
    "space": "a sky-blue adventure jacket with a small star patch",
    "dinosaurs": "a leaf-green explorer vest with a tiny footprint patch",
    "animals": "a warm yellow hoodie with a small paw-shaped patch",
    "sports": "a bright red jersey with a small circle badge",
    "friendship": "a soft blue sweater with a small heart-shaped patch",
}


def _split_secondary_name(child_name: str) -> tuple[str, str]:
    name = (child_name or "").strip()
    if not name:
        return "the child", ""

    match = re.search(r"\(([^)]+)\)", name)
    if match:
        primary = (name[: match.start()] + name[match.end() :]).strip()
        return primary or name, match.group(1).strip()

    if "/" in name:
        primary, secondary = [part.strip() for part in name.split("/", 1)]
        return primary or name, secondary

    return name, ""


def _resolve_outfit(request: StoryPipelineRequest) -> str:
    combined = " ".join(
        part.lower()
        for part in (request.theme, request.interest or "", request.tone_hint)
        if part
    )
    if "bean" in combined or "콩" in combined or "bean" in request.child_name.lower():
        return "blue-and-yellow striped pajamas with green cuffs and a small bean-shaped patch on the chest"
    for keyword, outfit in _FALLBACK_OUTFITS.items():
        if keyword in combined:
            return outfit
    return "a blue-and-yellow everyday outfit with green cuffs and a small round patch on the chest"


def build_character_bible(request: StoryPipelineRequest) -> CharacterBible:
    primary_name, secondary_name = _split_secondary_name(request.child_name)
    display_name = primary_name
    if secondary_name:
        display_name = f"{primary_name} / {secondary_name}"

    age_text = f"{request.child_age}-year-old" if request.child_age else "young"
    outfit = _resolve_outfit(request)
    fixed_design = (
        f"{display_name} is always the same {age_text} child with a round face, "
        "a consistent warm skin tone, rosy cheeks, bright brown almond-shaped eyes, "
        "thick soft eyebrows, a small button nose, a tiny mole under the left eye, "
        "and short dark-brown bowl-cut hair with two small cowlicks on top. "
        f"{display_name} always wears {outfit}. "
        "Keep the same childlike body proportions, head shape, facial structure, "
        "hair silhouette, outfit colors, and signature mole in every illustration."
    )

    forbidden = [
        "different hairstyle",
        "different face shape",
        "different eye shape",
        "missing mole under the left eye",
        "different outfit",
        "different age",
        "different ethnicity",
        "different body proportions",
    ]
    consistency_prompt = (
        "CHARACTER CONSISTENCY LOCK: Depict the protagonist with the exact same "
        "face, haircut, hair color, eye shape, mole under the left eye, outfit, "
        "body proportions, and character identity in every illustration. "
        "Do not change hairstyle, facial structure, outfit, age, ethnicity, or "
        "body proportions. Only change pose, expression, camera angle, and scene action. "
        f"Fixed character design: {fixed_design}"
    )

    return CharacterBible(
        name_primary=primary_name,
        name_secondary=secondary_name,
        age=request.child_age,
        fixed_design=fixed_design,
        art_consistency_prompt=consistency_prompt,
        forbidden_variations=forbidden,
    )
