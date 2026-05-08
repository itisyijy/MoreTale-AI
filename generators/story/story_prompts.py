from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "prompts"


@dataclass
class StoryPrompt:
    system_instruction_path: str = field(
        default_factory=lambda: str(PROMPTS_DIR / "system_instruction.txt")
    )
    user_prompt_path: str = field(
        default_factory=lambda: str(PROMPTS_DIR / "user_prompt.txt")
    )
    style_guide_path: str = field(
        default_factory=lambda: str(PROMPTS_DIR / "style_guide.txt")
    )
    include_style_guide: bool = True

    _system_instruction: Optional[str] = field(init=False, repr=False, default=None)
    _user_prompt_template: Optional[str] = field(init=False, repr=False, default=None)

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
            system_instruction = self._read_text(
                self.system_instruction_path, "System instruction"
            )
            style_guide = self._read_text(self.style_guide_path, "Style guide")
            system_instruction = f"{system_instruction}\n\n---\n\n{style_guide}"

            self._system_instruction = system_instruction
        return self._system_instruction

    def generate_user_prompt(
        self,
        child_name: str,
        primary_lang: str,
        secondary_lang: str,
        theme: str,
        extra_prompt: str = "",
        child_age: Optional[int] = None,
        primary_proficiency: str = "native",
        secondary_proficiency: str = "beginner",
        cultures: str = "",
        foreign_terms: str = "",
        style_preset: str = "vibrant_storybook",
        page_count: int = 32,
        tone_hint: str = "",
        gender: Optional[str] = None,
        family_situation: Optional[str] = None,
        interest: Optional[str] = None,
    ) -> str:
        if self._user_prompt_template is None:
            self._user_prompt_template = self._read_text(
                self.user_prompt_path, "User prompt"
            )

        from generators.story.module_loader import resolve_modules

        child_age_text = "" if child_age is None else str(child_age)
        cultures_resolved = cultures or f"{primary_lang}, {secondary_lang}"
        cultures_list = [c.strip() for c in cultures_resolved.split(",") if c.strip()]

        modules = resolve_modules(
            primary_lang=primary_lang,
            secondary_lang=secondary_lang,
            child_age=child_age,
            cultures=cultures_list,
            gender=gender,
            family_situation=family_situation,
            interest=interest,
        )

        try:
            return self._user_prompt_template.format(
                child_name=child_name,
                child_age=child_age_text,
                primary_lang=primary_lang,
                secondary_lang=secondary_lang,
                theme="" if theme is None else theme,
                extra_prompt=extra_prompt,
                primary_proficiency=primary_proficiency,
                secondary_proficiency=secondary_proficiency,
                cultures=cultures_resolved,
                foreign_terms=foreign_terms,
                style_preset=style_preset,
                page_count=page_count,
                tone_hint=tone_hint,
                **modules,
            )
        except KeyError as exc:
            raise ValueError(
                f"User prompt template has an unknown placeholder: {exc.args[0]}"
            ) from exc
