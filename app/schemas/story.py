from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

JobStatus = Literal["queued", "running", "completed", "failed", "canceled"]
AssetStatus = Literal[
    "not_requested",
    "generated",
    "skipped_exists",
    "skipped_empty_text",
    "failed",
    "missing",
]


class GenerationOptions(BaseModel):
    story_model: str = Field(default="gemini-2.5-flash")
    enable_quiz: bool = Field(default=False)
    quiz_model: str = Field(default="gemini-2.5-flash")
    quiz_question_count: int = Field(default=5, ge=1, le=10)
    enable_tts: bool = Field(default=False)
    tts_model: str = Field(default="gemini-2.5-flash-preview-tts")
    tts_voice: str = Field(default="Achernar")
    tts_temperature: float = Field(default=1.0)
    tts_request_interval_sec: float = Field(default=10.0)
    enable_illustration: bool = Field(default=False)
    enable_cover_illustration: bool = Field(default=True)
    illustration_model: str = Field(default="gemini-2.5-flash-image")
    illustration_aspect_ratio: str = Field(default="1:1")
    illustration_cover_aspect_ratio: str = Field(default="5:4")
    illustration_request_interval_sec: float = Field(default=1.0)
    illustration_skip_existing: bool = Field(default=True)

    @field_validator("story_model")
    @classmethod
    def validate_story_model(cls, value: str) -> str:
        normalized = value.strip()
        allowed = get_settings().allowed_story_models
        if normalized not in allowed:
            raise ValueError(f"story_model must be one of {list(allowed)}")
        return normalized

    @field_validator("quiz_model")
    @classmethod
    def validate_quiz_model(cls, value: str) -> str:
        normalized = value.strip()
        allowed = get_settings().allowed_quiz_models
        if normalized not in allowed:
            raise ValueError(f"quiz_model must be one of {list(allowed)}")
        return normalized

    @field_validator("tts_model")
    @classmethod
    def validate_tts_model(cls, value: str) -> str:
        normalized = value.strip()
        allowed = get_settings().allowed_tts_models
        if normalized not in allowed:
            raise ValueError(f"tts_model must be one of {list(allowed)}")
        return normalized

    @field_validator("illustration_model")
    @classmethod
    def validate_illustration_model(cls, value: str) -> str:
        normalized = value.strip()
        allowed = get_settings().allowed_illustration_models
        if normalized not in allowed:
            raise ValueError(f"illustration_model must be one of {list(allowed)}")
        return normalized


class StoryCreateRequest(BaseModel):
    child_name: str = Field(..., min_length=1)
    child_age: int | None = None
    primary_lang: str = Field(..., min_length=1)
    secondary_lang: str = Field(..., min_length=1)
    theme: str = ""
    extra_prompt: str = ""
    include_style_guide: bool = Field(
        default=True,
        description="Deprecated: prompts/style_guide.txt is always applied.",
    )
    generation: GenerationOptions = Field(default_factory=GenerationOptions)

    @field_validator("child_name")
    @classmethod
    def validate_child_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("child_name must not be empty")
        max_len = get_settings().child_name_max_len
        if len(normalized) > max_len:
            raise ValueError(f"child_name must be <= {max_len} characters")
        return normalized

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, value: str) -> str:
        normalized = value.strip()
        max_len = get_settings().theme_max_len
        if len(normalized) > max_len:
            raise ValueError(f"theme must be <= {max_len} characters")
        return normalized

    @field_validator("extra_prompt")
    @classmethod
    def validate_extra_prompt(cls, value: str) -> str:
        normalized = value.strip()
        max_len = get_settings().extra_prompt_max_len
        if len(normalized) > max_len:
            raise ValueError(f"extra_prompt must be <= {max_len} characters")
        return normalized

    @field_validator("include_style_guide", mode="before")
    @classmethod
    def force_include_style_guide(cls, value: Any) -> bool:
        del value
        return True

    @field_validator("primary_lang", "secondary_lang")
    @classmethod
    def validate_language(cls, value: str) -> str:
        _ISO_TO_LANGUAGE: dict[str, str] = {
            "ko": "Korean",
            "en": "English",
            "ja": "Japanese",
            "zh": "Chinese",
            "es": "Spanish",
            "vi": "Vietnamese",
            "fr": "French",
            "de": "German",
        }
        normalized = value.strip()
        if not normalized:
            raise ValueError("language must not be empty")
        normalized = _ISO_TO_LANGUAGE.get(normalized.lower(), normalized)
        allowed = get_settings().allowed_languages
        allowed_map = {item.lower(): item for item in allowed}
        mapped = allowed_map.get(normalized.lower())
        if mapped is None:
            raise ValueError(f"language must be one of {list(allowed)}")
        return mapped


class StoryCreateAcceptedResponse(BaseModel):
    id: str
    status: JobStatus
    status_url: str
    result_url: str


class StoryError(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: StoryError


class StoryStatusResponse(BaseModel):
    id: str
    status: JobStatus
    created_at: str
    updated_at: str
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: StoryError | None = None


class VocabularyPronunciationResponse(BaseModel):
    primary_url: str | None = None
    secondary_url: str | None = None
    primary_status: AssetStatus = "not_requested"
    primary_error: str | None = None
    secondary_status: AssetStatus = "not_requested"
    secondary_error: str | None = None
    has_primary_audio: bool = False
    has_secondary_audio: bool = False


class VocabularyEntryResponse(BaseModel):
    entry_id: str = ""
    primary_word: str
    secondary_word: str
    primary_definition: str = ""
    secondary_definition: str = ""
    pronunciation: VocabularyPronunciationResponse = Field(
        default_factory=VocabularyPronunciationResponse
    )


class StoryPageResponse(BaseModel):

    page_number: int
    text_primary: str
    text_secondary: str
    audio_primary_url: str | None = None
    audio_secondary_url: str | None = None
    illustration_url: str | None = None
    audio_primary_status: AssetStatus = "not_requested"
    audio_primary_error: str | None = None
    audio_secondary_status: AssetStatus = "not_requested"
    audio_secondary_error: str | None = None
    illustration_status: AssetStatus = "not_requested"
    illustration_error: str | None = None
    illustration_prompt: str = ""
    illustration_scene_prompt: str = ""
    has_primary_audio: bool = False
    has_secondary_audio: bool = False
    has_illustration: bool = False
    vocabulary: list[VocabularyEntryResponse] = Field(default_factory=list)


class StoryResultMetaResponse(BaseModel):
    title_primary: str
    title_secondary: str
    primary_language: str
    secondary_language: str
    page_count: int


class StoryAssetSummaryResponse(BaseModel):
    enabled: bool
    total_tasks: int
    generated: int
    skipped: int
    failed: int
    aspect_ratio: str | None = None
    manifest_url: str | None = None
    service_error: str | None = None


class StoryCoverAssetResponse(BaseModel):
    enabled: bool = False
    url: str | None = None
    status: AssetStatus = "not_requested"
    error: str | None = None
    prompt: str = ""
    aspect_ratio: str = "5:4"
    has_cover: bool = False


class StoryAssetsResponse(BaseModel):
    tts: StoryAssetSummaryResponse
    illustrations: StoryAssetSummaryResponse
    cover: StoryCoverAssetResponse
    has_partial_failures: bool


class StoryResultResponse(BaseModel):
    id: str
    status: JobStatus
    story_json_url: str | None = None
    quiz_json_url: str | None = None
    assets: StoryAssetsResponse
    meta: StoryResultMetaResponse
    pages: list[StoryPageResponse]
