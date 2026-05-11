from __future__ import annotations

import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
MODULES_DIR = PROMPTS_DIR / "modules"

_APPLY_WHEN_RE = re.compile(
    r"^## Apply when\s*\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL
)


def _load(rel_path: str) -> str:
    p = MODULES_DIR / rel_path
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    return _APPLY_WHEN_RE.sub("", text).strip()


def _age_band(age: int | None) -> str:
    if age is None or age <= 5:
        return "3-5"
    if age <= 8:
        return "6-8"
    return "9-12"


def resolve_modules(
    primary_lang: str,
    secondary_lang: str,
    child_age: int | None,
    cultures: list[str],
    gender: str | None,
    family_situation: str | None,
    interest: str | None,
) -> dict[str, str]:
    inclusive = _load("gender/inclusive.txt")
    if gender == "male":
        gender_text = _load("gender/boys.txt") + "\n\n" + inclusive
    elif gender == "female":
        gender_text = _load("gender/girls.txt") + "\n\n" + inclusive
    else:
        gender_text = inclusive

    return {
        "module_language_primary": _load(f"language/{primary_lang.lower()}.txt"),
        "module_language_secondary": _load(f"language/{secondary_lang.lower()}.txt"),
        "module_age": _load(f"age/{_age_band(child_age)}.txt"),
        "module_gender": gender_text,
        "module_family": _load(f"family/{family_situation}.txt") if family_situation else "",
        "module_interest": _load(f"interest/{interest.lower()}.txt") if interest else "",
        "module_culture_primary": _load(f"culture/{cultures[0].lower()}.txt") if cultures else "",
        "module_culture_secondary": (
            _load(f"culture/{cultures[1].lower()}.txt") if len(cultures) > 1 else ""
        ),
    }
