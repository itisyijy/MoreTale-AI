from __future__ import annotations

from app.core.languages import resolve_language_name, to_story_iso
from app.core.config import get_settings
from app.schemas.story import (
    AgeGroup,
    FamilyConfiguration,
    FamilyStructure,
    Gender,
    GeneratedSlide,
    LanguageProficiency,
    StoryGenerateRequest,
    StoryGenerateResponse,
    StoryPreference,
)
from app.services.generation_pipeline import StoryPipelineRequest
from generators.story.story_model import Story

PageAssetUrlMap = dict[int, dict[str, str | None]]

_AGE_GROUP_TO_INT: dict[AgeGroup, int] = {
    AgeGroup.AGE_0_2: 1,
    AgeGroup.AGE_3_4: 3,
    AgeGroup.AGE_5_6: 5,
    AgeGroup.AGE_7_8: 7,
    AgeGroup.AGE_9_10: 9,
    AgeGroup.AGE_10_PLUS: 10,
}

# Writing guidance per proficiency level
_PROFICIENCY_WRITING_GUIDE: dict[LanguageProficiency, dict[str, str]] = {
    LanguageProficiency.EGG: {
        "label": "Complete Beginner (EGG)",
        "guidance": (
            "Use only the most common, everyday vocabulary. "
            "Keep sentences extremely short (3–5 words). "
            "Repeat key words many times across pages. "
            "Use simple present tense only. "
            "Prioritize visual-contextual language the child can guess from pictures."
        ),
    },
    LanguageProficiency.LARVA: {
        "label": "Basic (LARVA)",
        "guidance": (
            "Use high-frequency vocabulary with occasional new words supported by context. "
            "Keep sentences short (5–7 words). "
            "Repeat important vocabulary across as many pages as the configured page count allows. "
            "Use simple present and simple past tense. "
            "Avoid idioms or culturally specific expressions."
        ),
    },
    LanguageProficiency.PUPA: {
        "label": "Intermediate (PUPA)",
        "guidance": (
            "Mix familiar vocabulary with 2–3 new words per page, introduced in context. "
            "Use medium-length sentences (7–10 words). "
            "Compound sentences are acceptable occasionally. "
            "Include present, past, and future tenses. "
            "Light use of idiomatic expressions is fine."
        ),
    },
    LanguageProficiency.BEE: {
        "label": "Advanced (BEE)",
        "guidance": (
            "Use rich, expressive vocabulary including idiomatic and culturally nuanced expressions. "
            "Sentences can be longer (8–12 words) with varied structure. "
            "Include complex sentence forms, varied tenses, and literary devices. "
            "Introduce 3–5 new advanced words per page with embedded context clues. "
            "Language should be as rich and natural as a native children's book."
        ),
    },
}

# Skill-specific guidance
_SKILL_GUIDANCE: dict[str, str] = {
    "listening": (
        "Prioritize rhythm, repetition, and read-aloud flow. "
        "Use onomatopoeia, predictable phrase patterns, and musical sentence structure."
    ),
    "speaking": (
        "Include natural dialogue and character speech. "
        "Use conversational phrasing that is easy to repeat aloud. "
        "Add call-and-response moments or repeated refrains."
    ),
}

# Story atmosphere per preference
_PROFICIENCY_TO_LABEL: dict[LanguageProficiency, str] = {
    LanguageProficiency.EGG: "beginner",
    LanguageProficiency.LARVA: "beginner",
    LanguageProficiency.PUPA: "intermediate",
    LanguageProficiency.BEE: "fluent",
}

_LEGACY_FAMILY_TO_MODULE: dict[FamilyConfiguration, str] = {
    FamilyConfiguration.KOREAN_PATERNAL: "multicultural_korean_paternal",
    FamilyConfiguration.KOREAN_MATERNAL: "multicultural_korean_maternal",
    FamilyConfiguration.DUAL_FOREIGN: "multicultural_dual_foreign",
    FamilyConfiguration.BLENDED: "multicultural_blended",
    FamilyConfiguration.SINGLE_PARENT: "single_parent",
}

_FAMILY_STRUCTURE_TO_MODULE: dict[FamilyStructure, str] = {
    FamilyStructure.ONE_PARENT: "single_parent",
}

_FAMILY_STRUCTURE_LABELS: dict[FamilyStructure, str] = {
    FamilyStructure.ONE_PARENT: "one-parent family",
    FamilyStructure.TWO_PARENTS: "two-parent family",
    FamilyStructure.EXTENDED_FAMILY: "extended family",
    FamilyStructure.SECRET: "family structure not disclosed",
}

_PREFERENCE_TO_TONE: dict[StoryPreference, str] = {
    StoryPreference.WARM_HUG: "warm and comforting",
    StoryPreference.FUN_ADVENTURE: "festive and adventurous",
    StoryPreference.DAILY_LIFE: "quiet and reflective",
    StoryPreference.CUSTOM: "",
}

_PREFERENCE_ATMOSPHERE: dict[StoryPreference, str] = {
    StoryPreference.WARM_HUG: (
        "Warm and comforting atmosphere. "
        "Focus on family bonds, emotional safety, and gentle moments. "
        "Use soft sensory language (warmth, softness, cozy light). "
        "Slow, nurturing pacing — linger on emotional beats."
    ),
    StoryPreference.FUN_ADVENTURE: (
        "High-energy, exciting, and action-packed atmosphere. "
        "Include discovery moments, age-appropriate dangers, and triumphant victories. "
        "Use vivid action verbs and fast pacing. "
        "Keep the child feeling like a hero throughout."
    ),
    StoryPreference.DAILY_LIFE: (
        "Grounded in relatable everyday situations (school, meals, bedtime, friendship). "
        "Use realistic, familiar settings the child recognizes from daily life. "
        "Emotional stakes should feel true-to-life rather than fantastical. "
        "Quiet humor and small victories work well."
    ),
    StoryPreference.CUSTOM: "",
}


def _build_extra_prompt(req: StoryGenerateRequest) -> str:
    """
    Builds the extra_prompt field for detailed skill-level writing guidance.
    The proficiency level labels themselves go into dedicated primary/secondary_proficiency
    fields. This field carries per-skill notes and any additional adaptation context.
    """
    sections: list[str] = []

    primary_name = resolve_language_name(req.primary_language)
    secondary_name = resolve_language_name(req.secondary_language)

    # Per-skill listening/speaking guidance (supplements the level label)
    skill_lines: list[str] = []
    if req.first_language_listening:
        label = _PROFICIENCY_WRITING_GUIDE[req.first_language_listening]["label"]
        skill_lines.append(
            f"{primary_name} listening: {label} — {_SKILL_GUIDANCE['listening']}"
        )
    if req.first_language_speaking:
        label = _PROFICIENCY_WRITING_GUIDE[req.first_language_speaking]["label"]
        skill_lines.append(
            f"{primary_name} speaking: {label} — {_SKILL_GUIDANCE['speaking']}"
        )
    if req.second_language_listening:
        label = _PROFICIENCY_WRITING_GUIDE[req.second_language_listening]["label"]
        skill_lines.append(
            f"{secondary_name} listening: {label} — {_SKILL_GUIDANCE['listening']}"
        )
    if req.second_language_speaking:
        label = _PROFICIENCY_WRITING_GUIDE[req.second_language_speaking]["label"]
        skill_lines.append(
            f"{secondary_name} speaking: {label} — {_SKILL_GUIDANCE['speaking']}"
        )
    if skill_lines:
        sections.append("[Skill-level notes]\n" + "\n".join(f"  {l}" for l in skill_lines))

    # Traditional tale adaptation note
    if req.recommended_tale_title:
        sections.append(
            f"[Traditional Tale]\n"
            f"  Adapt the traditional tale: «{req.recommended_tale_title}».\n"
            f"  Preserve the core moral and key story beats while making it accessible "
            f"to the child's age group. Incorporate elements from both cultures naturally."
        )

    profile_lines = _build_profile_context_lines(req)
    if profile_lines:
        sections.append("[Profile context]\n" + "\n".join(f"  {l}" for l in profile_lines))

    return "\n\n".join(sections)


def _build_theme(req: StoryGenerateRequest) -> str:
    parts: list[str] = []

    # autoGenerated: recommendedTaleTitle takes priority as the theme
    if req.auto_generated and req.recommended_tale_title:
        parts.append(f"Adapt the traditional tale: «{req.recommended_tale_title}».")
        if req.prompt:
            parts.append(f"Additional context: {req.prompt}")
        return "\n".join(parts)

    # Story preference atmosphere
    if req.story_preference == StoryPreference.CUSTOM:
        if req.custom_story_preference:
            parts.append(f"Style: {req.custom_story_preference}")
    elif req.story_preference:
        atmosphere = _PREFERENCE_ATMOSPHERE.get(req.story_preference, "")
        if atmosphere:
            parts.append(f"Atmosphere / style: {atmosphere}")

    # User prompt
    if req.prompt:
        parts.append(f"Topic / theme: {req.prompt}")

    return "\n".join(parts)


def _build_profile_context_lines(req: StoryGenerateRequest) -> list[str]:
    lines: list[str] = []
    if req.family_structure == FamilyStructure.CUSTOM and req.custom_family_structure:
        lines.append(f"Family structure: {req.custom_family_structure}.")
    elif req.family_structure:
        label = _FAMILY_STRUCTURE_LABELS.get(req.family_structure)
        if label:
            lines.append(f"Family structure: {label}.")
    elif req.family_configuration:
        lines.append(f"Family configuration: {req.family_configuration.value}.")

    if req.child_nationality:
        lines.append(f"Child nationality: {req.child_nationality}.")
    if req.parent_country:
        lines.append(f"Parent country: {req.parent_country}.")
    return lines


def _resolve_family_situation(req: StoryGenerateRequest) -> str | None:
    if req.family_structure:
        return _FAMILY_STRUCTURE_TO_MODULE.get(req.family_structure)
    if req.family_configuration:
        return _LEGACY_FAMILY_TO_MODULE.get(req.family_configuration)
    return None


def _resolve_page_count(req: StoryGenerateRequest) -> int:
    _ = req
    return get_settings().story_page_count


def map_generate_request_to_pipeline(
    req: StoryGenerateRequest,
    story_model: str = "gemini-2.5-flash",
) -> StoryPipelineRequest:
    # Prefer explicit childAge sent by backend; fall back to ageGroup conversion
    child_age = req.child_age or (
        _AGE_GROUP_TO_INT.get(req.age_group) if req.age_group else None
    )

    primary_name = resolve_language_name(req.primary_language)
    secondary_name = resolve_language_name(req.secondary_language)

    primary_proficiency = (
        _PROFICIENCY_TO_LABEL.get(req.first_language_proficiency, "native")
        if req.first_language_proficiency else "native"
    )
    secondary_proficiency = (
        _PROFICIENCY_TO_LABEL.get(req.second_language_proficiency, "beginner")
        if req.second_language_proficiency else "beginner"
    )

    tone_hint = ""
    if req.story_preference == StoryPreference.CUSTOM and req.custom_story_preference:
        tone_hint = req.custom_story_preference
    elif req.story_preference:
        tone_hint = _PREFERENCE_TO_TONE.get(req.story_preference, "")

    gender = (
        "male" if req.gender == Gender.MALE
        else "female" if req.gender == Gender.FEMALE
        else None
    )
    family_situation = _resolve_family_situation(req)

    return StoryPipelineRequest(
        child_name=req.child_name or "주인공",
        child_age=child_age,
        primary_lang=primary_name,
        secondary_lang=secondary_name,
        theme=_build_theme(req),
        extra_prompt=_build_extra_prompt(req),
        primary_proficiency=primary_proficiency,
        secondary_proficiency=secondary_proficiency,
        cultures=f"{primary_name}, {secondary_name}",
        foreign_terms="",
        style_preset="vibrant_storybook",
        page_count=_resolve_page_count(req),
        tone_hint=tone_hint,
        gender=gender,
        family_situation=family_situation,
        interest=req.interest,
        story_model=story_model,
        enable_quiz=False,
        enable_tts=False,
        enable_illustration=False,
    )


def map_story_to_generate_response(
    story: Story,
    req: StoryGenerateRequest,
    page_assets: PageAssetUrlMap | None = None,
) -> StoryGenerateResponse:
    page_assets = page_assets or {}
    cover_assets = page_assets.get(0, {})
    has_cover_slide = bool(cover_assets.get("image_url"))
    slides: list[GeneratedSlide] = []

    if has_cover_slide:
        slides.append(
            GeneratedSlide(
                order=0,
                text_kr="",
                text_native="",
                image_url=cover_assets.get("image_url"),
                audio_url_kr=None,
                audio_url_native=None,
            )
        )

    for page in story.pages:
        assets = page_assets.get(page.page_number, {})
        slides.append(
            GeneratedSlide(
                order=page.page_number if has_cover_slide else page.page_number - 1,
                text_kr=page.text_primary,
                text_native=page.text_secondary,
                image_url=assets.get("image_url"),
                audio_url_kr=assets.get("audio_url_kr"),
                audio_url_native=assets.get("audio_url_native"),
            )
        )

    # Always return lowercase ISO codes — backend Swagger examples use ko/vi/en.
    primary_iso = to_story_iso(req.primary_language) or to_story_iso(story.primary_language)
    secondary_iso = to_story_iso(req.secondary_language) or to_story_iso(story.secondary_language)

    return StoryGenerateResponse(
        title=story.title_primary,
        child_name=req.child_name or story.author_name,
        primary_language=primary_iso or story.primary_language,
        secondary_language=secondary_iso or story.secondary_language,
        slides=slides,
    )
