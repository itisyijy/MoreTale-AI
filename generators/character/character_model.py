from __future__ import annotations

from pydantic import BaseModel, Field


class CharacterBible(BaseModel):
    """Runtime-only visual contract for the protagonist.

    This model intentionally stays outside the public story response contract.
    It is used to make story prompts and image prompts describe the same fixed
    character without adding backend-facing fields.
    """

    name_primary: str = Field(default="")
    name_secondary: str = Field(default="")
    age: int | None = None
    role: str = Field(default="main character")
    fixed_design: str
    art_consistency_prompt: str
    forbidden_variations: list[str] = Field(default_factory=list)
