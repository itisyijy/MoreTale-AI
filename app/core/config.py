from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < 1:
        return default
    return value


def _parse_csv_env(name: str, default: list[str]) -> tuple[str, ...]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return tuple(default)
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values if values else tuple(default)


@dataclass(frozen=True)
class Settings:
    api_keys: tuple[str, ...]
    project_root: Path
    outputs_dir: Path
    static_outputs_prefix: str = "/static/outputs"
    # Storage backend: "local" (default) or "gcs"
    storage_backend: str = "local"
    gcs_bucket: str = ""
    gcs_key_prefix: str = ""
    rate_limit_post_stories_per_min: int = 5
    theme_max_len: int = 120
    extra_prompt_max_len: int = 2000
    child_name_max_len: int = 40
    allowed_story_models: tuple[str, ...] = ("gemini-2.5-flash",)
    allowed_quiz_models: tuple[str, ...] = ("gemini-2.5-flash",)
    allowed_critic_models: tuple[str, ...] = ("gemini-2.5-flash",)
    allowed_tts_models: tuple[str, ...] = ("gemini-2.5-flash-preview-tts",)
    allowed_illustration_models: tuple[str, ...] = ("gemini-2.5-flash-image",)
    allowed_languages: tuple[str, ...] = (
        "Korean",
        "English",
        "Japanese",
        "Chinese",
        "Spanish",
        "Vietnamese",
        "French",
        "German",
    )

    @property
    def api_key(self) -> str:
        return self.api_keys[0] if self.api_keys else ""


def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    outputs_override = (os.getenv("MORETALE_OUTPUTS_DIR") or "").strip()
    outputs_dir = (
        Path(outputs_override).resolve() if outputs_override else project_root / "outputs"
    )
    api_keys = _parse_csv_env("MORETALE_API_KEY", default=[])
    storage_backend = (os.getenv("MORETALE_STORAGE_BACKEND") or "local").strip().lower()
    gcs_bucket = (os.getenv("MORETALE_GCS_BUCKET") or "").strip()
    gcs_key_prefix = (os.getenv("MORETALE_GCS_KEY_PREFIX") or "").strip()
    return Settings(
        api_keys=api_keys,
        project_root=project_root,
        outputs_dir=outputs_dir,
        storage_backend=storage_backend,
        gcs_bucket=gcs_bucket,
        gcs_key_prefix=gcs_key_prefix,
        rate_limit_post_stories_per_min=_parse_int_env(
            "MORETALE_RATE_LIMIT_POST_STORIES_PER_MIN",
            default=5,
        ),
        theme_max_len=_parse_int_env("MORETALE_THEME_MAX_LEN", default=120),
        extra_prompt_max_len=_parse_int_env(
            "MORETALE_EXTRA_PROMPT_MAX_LEN",
            default=2000,
        ),
        child_name_max_len=_parse_int_env("MORETALE_CHILD_NAME_MAX_LEN", default=40),
        allowed_story_models=_parse_csv_env(
            "MORETALE_ALLOWED_STORY_MODELS",
            default=["gemini-2.5-flash"],
        ),
        allowed_quiz_models=_parse_csv_env(
            "MORETALE_ALLOWED_QUIZ_MODELS",
            default=["gemini-2.5-flash"],
        ),
        allowed_critic_models=_parse_csv_env(
            "MORETALE_ALLOWED_CRITIC_MODELS",
            default=["gemini-2.5-flash"],
        ),
        allowed_tts_models=_parse_csv_env(
            "MORETALE_ALLOWED_TTS_MODELS",
            default=["gemini-2.5-flash-preview-tts"],
        ),
        allowed_illustration_models=_parse_csv_env(
            "MORETALE_ALLOWED_ILLUSTRATION_MODELS",
            default=["gemini-2.5-flash-image"],
        ),
        allowed_languages=_parse_csv_env(
            "MORETALE_ALLOWED_LANGUAGES",
            default=[
                "Korean",
                "English",
                "Japanese",
                "Chinese",
                "Spanish",
                "Vietnamese",
                "French",
                "German",
            ],
        ),
    )
