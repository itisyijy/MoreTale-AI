import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from generators.story.story_model import Story

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "prompts"


@dataclass
class QuizPrompt:
    system_instruction_path: str = field(
        default_factory=lambda: str(PROMPTS_DIR / "quiz_system_instruction.txt")
    )
    user_prompt_path: str = field(
        default_factory=lambda: str(PROMPTS_DIR / "quiz_user_prompt.txt")
    )

    _system_instruction: str | None = field(init=False, repr=False, default=None)
    _user_prompt_template: str | None = field(init=False, repr=False, default=None)

    @staticmethod
    def _read_text(path: str, label: str) -> str:
        file_path = Path(path)
        try:
            return file_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"{label} file not found at {file_path}") from exc

    @property
    def system_instruction(self) -> str:
        if self._system_instruction is None:
            self._system_instruction = self._read_text(
                self.system_instruction_path, "Quiz system instruction"
            )
        return self._system_instruction

    def generate_user_prompt(
        self,
        *,
        story_id: str,
        story: Story,
        question_count: int,
    ) -> str:
        if self._user_prompt_template is None:
            self._user_prompt_template = self._read_text(
                self.user_prompt_path, "Quiz user prompt"
            )

        story_context = self._build_story_context(story)
        try:
            return self._user_prompt_template.format(
                story_id=story_id,
                story_title_primary=story.title_primary,
                story_title_secondary=story.title_secondary,
                primary_language=story.primary_language,
                secondary_language=story.secondary_language,
                question_count=question_count,
                story_context=story_context,
            )
        except KeyError as exc:
            raise ValueError(
                f"Quiz user prompt template has an unknown placeholder: {exc.args[0]}"
            ) from exc

    @staticmethod
    def _build_story_context(story: Story) -> str:
        pages: list[dict[str, Any]] = []
        for page in story.pages:
            pages.append(
                {
                    "page_number": page.page_number,
                    "text_primary": page.text_primary,
                    "text_secondary": page.text_secondary,
                    "vocabulary": [
                        {
                            "entry_id": entry.entry_id or "",
                            "primary_word": entry.primary_word,
                            "secondary_word": entry.secondary_word,
                            "primary_definition": entry.primary_definition,
                            "secondary_definition": entry.secondary_definition,
                        }
                        for entry in page.vocabulary
                    ],
                }
            )

        return json.dumps(pages, ensure_ascii=False, indent=2)
