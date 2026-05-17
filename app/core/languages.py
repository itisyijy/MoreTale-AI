"""Shared language and locale normalization helpers."""

from __future__ import annotations

from collections.abc import Iterable

ISO_TO_LANGUAGE = {
    "ko": "Korean",
    "en": "English",
    "ja": "Japanese",
    "zh": "Chinese",
    "es": "Spanish",
    "vi": "Vietnamese",
    "fr": "French",
    "de": "German",
}

LANGUAGE_NAME_TO_ISO = {language.lower(): iso for iso, language in ISO_TO_LANGUAGE.items()}
KNOWN_STORY_LANGUAGE_CODES = frozenset(ISO_TO_LANGUAGE)

TTS_LOCALE_TO_CANONICAL = {
    "ko-kr": "ko-KR",
    "en-us": "en-US",
    "en-gb": "en-GB",
    "ja-jp": "ja-JP",
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "es-es": "es-ES",
    "vi-vn": "vi-VN",
    "fr-fr": "fr-FR",
    "de-de": "de-DE",
}


def normalize_story_language_code(value: str | None) -> str | None:
    """Normalize known story ISO codes while preserving unknown values."""

    if value is None:
        return value
    normalized = value.strip()
    lower = normalized.lower()
    return lower if lower in KNOWN_STORY_LANGUAGE_CODES else normalized


def resolve_language_name(value: str | None, default: str = "Korean") -> str:
    """Return the prompt-facing language name for an ISO code or language name."""

    if value is None:
        return default
    normalized = value.strip()
    if not normalized:
        return default
    return ISO_TO_LANGUAGE.get(normalized.lower(), normalized)


def to_story_iso(value: str | None) -> str | None:
    """Convert known story language names and codes to ISO codes."""

    if value is None:
        return None
    normalized = value.strip()
    lower = normalized.lower()
    if lower in ISO_TO_LANGUAGE:
        return lower
    if lower in LANGUAGE_NAME_TO_ISO:
        return LANGUAGE_NAME_TO_ISO[lower]
    return normalized


def coerce_allowed_language(value: str, allowed_languages: Iterable[str]) -> str | None:
    """Map ISO codes or language names to the configured allowed language value."""

    normalized = resolve_language_name(value, default="")
    if not normalized:
        return None
    allowed_map = {item.lower(): item for item in allowed_languages}
    return allowed_map.get(normalized.lower())


def normalize_tts_locale(value: str) -> str:
    """Canonicalize known TTS locales while preserving custom locale values."""

    normalized = value.strip()
    return TTS_LOCALE_TO_CANONICAL.get(normalized.lower(), normalized)
