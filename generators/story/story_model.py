from typing import List

from pydantic import BaseModel, Field, field_validator

STORY_PAGE_COUNT = 32


class VocabularyEntry(BaseModel):
    entry_id: str | None = Field(
        default=None,
        description=(
            "Stable page-local identifier for the vocabulary entry. The application "
            "may populate this automatically when the model omits it."
        ),
    )
    primary_word: str = Field(
        ...,
        description="Core word or short phrase in the primary language.",
    )
    secondary_word: str = Field(
        ...,
        description="Aligned translation of the same word or short phrase.",
    )
    primary_definition: str = Field(
        ...,
        description="Child-friendly definition in the primary language.",
    )
    secondary_definition: str = Field(
        ...,
        description="Child-friendly definition in the secondary language.",
    )


class Page(BaseModel):
    page_number: int = Field(..., description=f"Page number from 1 to {STORY_PAGE_COUNT}")
    text_primary: str = Field(
        ..., description="Story text in the primary language (Child's context)"
    )
    text_secondary: str = Field(
        ..., description="Story text in the secondary language (Parent's context)"
    )
    illustration_prompt: str = Field(
        ...,
        description=(
            "Detailed description for an AI image generator. MUST include the "
            "character's visual features defined in the Story class."
        ),
    )
    illustration_scene_prompt: str | None = Field(
        default=None,
        description=(
            "Page-specific scene description derived from illustration_prompt after "
            "removing the global illustration_prefix/main_character_design. Intended "
            "for reuse with a shared prefix when generating images."
        ),
    )
    vocabulary: List[VocabularyEntry] = Field(
        default_factory=list,
        description=(
            "Page-specific bilingual vocabulary pairs with short definitions that help "
            "the child learn core words from the page."
        ),
    )


class Story(BaseModel):
    title_primary: str = Field(..., description="Title in primary language")
    title_secondary: str = Field(..., description="Title in secondary language")
    author_name: str = Field(..., description="Name of the author (AI or Child's name)")
    primary_language: str = Field(..., description="Primary language of the story text")
    secondary_language: str = Field(
        ..., description="Secondary language of the story text"
    )

    image_style: str = Field(
        ...,
        description=(
            "The consistent art style for the entire book "
            "(e.g., 'Soft watercolor', 'Vibrant digital art')."
        ),
    )
    main_character_design: str = Field(
        ...,
        description=(
            "Physical description of the main character (e.g., 'A 5-year-old Korean "
            "boy with short black hair, wearing a red t-shirt'). This MUST be used in "
            "every page's illustration prompt."
        ),
    )
    illustration_prefix: str | None = Field(
        default=None,
        description=(
            "Global illustration prefix composed from image_style and "
            "main_character_design (e.g., '{image_style}, {main_character_design}'). "
            "This may be populated by the application for reuse across pages."
        ),
    )
    cover_illustration_prompt: str | None = Field(
        default=None,
        description=(
            "Application-generated prompt for the book cover illustration. This is "
            "derived from the story-level illustration style and representative page "
            "scenes so the cover can be generated alongside the interior images."
        ),
    )

    pages: List[Page] = Field(
        ...,
        description=f"List of exactly {STORY_PAGE_COUNT} pages",
    )

    @field_validator("pages")
    def check_page_count(cls, value):
        if len(value) != STORY_PAGE_COUNT:
            raise ValueError(
                f"Story must have exactly {STORY_PAGE_COUNT} pages, but got {len(value)}"
            )
        return value
