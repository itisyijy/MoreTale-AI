import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

QuizQuestionType = Literal["multiple_choice"]

# VOCABULARY: tests a word from the story in context
# STORY: covers comprehension, cause-and-effect, emotion, sequence
QuizSkill = Literal["VOCABULARY", "STORY"]

_VALID_CHOICE_IDS = {"1", "2", "3", "4"}
_QUESTION_NUMBER_LABEL = (
    r"(?:(?:문제|문항)\s*\d+\s*(?:번)?|(?:question|q)\s*#?\s*\d+)"
)
_QUESTION_NUMBER_PREFIX_RES = (
    re.compile(
        rf"^\s*(?:[\(\[（［]\s*)?{_QUESTION_NUMBER_LABEL}\s*(?:[\)\]）］])?"
        r"\s*[:：.\-–—]?\s*",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*\d+\s*[\.\)]\s*"),
)
_QUESTION_NUMBER_SUFFIX_RES = (
    re.compile(rf"\s*[\(\[（［]\s*{_QUESTION_NUMBER_LABEL}\s*[\)\]）］]\s*$", re.IGNORECASE),
    re.compile(rf"\s+{_QUESTION_NUMBER_LABEL}\s*[:：.]?\s*$", re.IGNORECASE),
)


class QuizChoice(BaseModel):
    choice_id: str = Field(..., description="Choice identifier: 1, 2, 3, or 4.")
    text: str = Field(..., min_length=1, description="Choice text shown to the child.")

    @field_validator("choice_id")
    @classmethod
    def normalize_choice_id(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in _VALID_CHOICE_IDS:
            raise ValueError(f"choice_id must be one of {sorted(_VALID_CHOICE_IDS)}")
        return normalized


class QuizAnswer(BaseModel):
    choice_id: str = Field(..., description="Correct choice identifier (1, 2, 3, or 4).")
    text: str = Field(..., min_length=1, description="Correct choice text.")

    @field_validator("choice_id")
    @classmethod
    def normalize_choice_id(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in _VALID_CHOICE_IDS:
            raise ValueError(f"choice_id must be one of {sorted(_VALID_CHOICE_IDS)}")
        return normalized


class QuizQuestion(BaseModel):
    question_id: str = Field(..., description="Stable question identifier such as q1.")
    type: QuizQuestionType = Field(default="multiple_choice")
    skill: QuizSkill
    question_text: str = Field(..., min_length=1)
    choices: list[QuizChoice] = Field(
        ..., min_length=4, max_length=4, description="Exactly 4 multiple-choice options."
    )
    answer: QuizAnswer
    explanation: str = Field(..., min_length=1)
    source_page_numbers: list[int] = Field(
        ..., min_length=1, description="Pages that justify the answer."
    )
    source_vocabulary_entry_ids: list[str] = Field(default_factory=list)

    @field_validator("question_id")
    @classmethod
    def normalize_question_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question_id must not be empty")
        return normalized

    @field_validator("question_text")
    @classmethod
    def normalize_question_text(cls, value: str) -> str:
        normalized = value.strip()
        for pattern in _QUESTION_NUMBER_PREFIX_RES:
            normalized = pattern.sub("", normalized).strip()
        for pattern in _QUESTION_NUMBER_SUFFIX_RES:
            normalized = pattern.sub("", normalized).strip()
        if not normalized:
            raise ValueError("question_text must not be empty")
        return normalized

    @field_validator("source_page_numbers")
    @classmethod
    def validate_source_page_numbers(cls, value: list[int]) -> list[int]:
        if any(page_number < 1 for page_number in value):
            raise ValueError("source_page_numbers must be positive page numbers")
        return value

    @field_validator("source_vocabulary_entry_ids")
    @classmethod
    def normalize_source_vocabulary_entry_ids(cls, value: list[str]) -> list[str]:
        return [entry_id.strip() for entry_id in value if entry_id.strip()]

    @model_validator(mode="after")
    def validate_answer_matches_choices(self) -> "QuizQuestion":
        choice_ids = {choice.choice_id for choice in self.choices}
        if self.answer.choice_id not in choice_ids:
            raise ValueError("answer.choice_id must match one of the choices")

        matching_choice = next(
            choice for choice in self.choices if choice.choice_id == self.answer.choice_id
        )
        if self.answer.text.strip() != matching_choice.text.strip():
            raise ValueError("answer.text must match the correct choice text")
        return self


class Quiz(BaseModel):
    story_id: str = Field(..., min_length=1)
    story_title_primary: str = Field(..., min_length=1)
    story_title_secondary: str = Field(..., min_length=1)
    primary_language: str = Field(..., min_length=1)
    secondary_language: str = Field(..., min_length=1)
    question_count: int = Field(default=5, ge=1)
    questions: list[QuizQuestion] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_question_count(self) -> "Quiz":
        if self.question_count != len(self.questions):
            raise ValueError("question_count must match the number of questions")

        vocabulary_questions = [
            question
            for question in self.questions
            if question.skill == "VOCABULARY"
        ]
        if not vocabulary_questions:
            raise ValueError("quiz must include at least one VOCABULARY question")
        if self.question_count == 5 and len(vocabulary_questions) != 1:
            raise ValueError("5-question quiz must include exactly one VOCABULARY question")
        return self
