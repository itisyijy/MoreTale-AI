from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.schemas.story import StoryError, StoryGenerateRequest

InternalJobType = Literal["story", "tts", "quiz", "vocab"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class InternalJobCreateResponse(CamelModel):
    job_id: str
    type: InternalJobType
    status: str
    status_url: str
    result_url: str
    callback_url: str


class InternalJobStatusResponse(CamelModel):
    job_id: str
    type: InternalJobType
    status: str
    created_at: str
    updated_at: str
    status_url: str
    result_url: str
    callback_url: str
    request_id: str | None = None
    error: StoryError | None = None


class InternalWebhookPayload(CamelModel):
    job_id: str
    type: InternalJobType
    status: Literal["completed", "failed"]
    result_url: str
    error: StoryError | None = None
    request_id: str | None = None


class InternalJobResultResponse(CamelModel):
    job_id: str
    type: InternalJobType
    status: str
    data: dict[str, Any] | list[Any] | None = None
    error: StoryError | None = None


class CallbackJobRequest(CamelModel):
    callback_url: str = Field(..., min_length=1)
    request_id: str | None = None

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("callback_url must start with http:// or https://")
        return normalized


class StoryInternalJobRequest(CallbackJobRequest, StoryGenerateRequest):
    """Async story request matching backend StoryGenerateRequest plus callbackUrl."""


class TTSInput(CamelModel):
    text: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    id: str | None = None


class TTSInternalJobRequest(CallbackJobRequest):
    text: str | None = None
    language: str | None = None
    inputs: list[TTSInput] | None = None
    model: str = "gemini-2.5-flash-preview-tts"
    voice: str = "Achernar"
    temperature: float = 1.0

    @model_validator(mode="after")
    def validate_single_or_batch(self) -> "TTSInternalJobRequest":
        has_single = bool((self.text or "").strip() and (self.language or "").strip())
        has_batch = bool(self.inputs)
        if has_single == has_batch:
            raise ValueError("provide either text/language or inputs")
        return self


class QuizInternalJobRequest(CallbackJobRequest):
    story_id: str = Field(..., min_length=1)
    story: dict[str, Any] | None = None
    story_json_url: str | None = None
    question_count: int = Field(default=5, ge=1, le=10)
    model: str = "gemini-2.5-flash"

    @model_validator(mode="after")
    def validate_story_source(self) -> "QuizInternalJobRequest":
        if (self.story is None) == (not self.story_json_url):
            raise ValueError("provide either story or storyJsonUrl")
        return self


class VocabSlideInput(CamelModel):
    order: int = Field(..., ge=0)
    text_kr: str = ""
    text_native: str = ""
    vocabulary: list[dict[str, Any]] = Field(default_factory=list)


class VocabInternalJobRequest(CallbackJobRequest):
    story_id: str | None = None
    primary_language: str = "ko"
    secondary_language: str = "en"
    slides: list[VocabSlideInput] = Field(..., min_length=1)
