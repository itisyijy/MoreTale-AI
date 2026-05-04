from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings

STORY_GLOB = "story_*.json"
QUIZ_GLOB = "quiz_*.json"


def ensure_outputs_dir() -> Path:
    outputs_dir = get_settings().outputs_dir
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return outputs_dir


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def slugify_language_name(text: str) -> str:
    slug = slugify(text)
    return slug or "language"


def make_story_id(child_name: str, theme: str = "") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    source = "-".join(part for part in [child_name.strip(), theme.strip()] if part)
    slug = slugify(source) or "story"
    base_story_id = f"{timestamp}_story_{slug}"

    outputs_dir = ensure_outputs_dir()
    story_id = base_story_id
    suffix = 1
    while (outputs_dir / story_id).exists():
        story_id = f"{base_story_id}-{suffix:02d}"
        suffix += 1
    return story_id


def get_run_dir(story_id: str) -> Path:
    return ensure_outputs_dir() / story_id


def write_story_json(story_id: str, story: Any, story_model: str) -> Path:
    run_dir = get_run_dir(story_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    story_json_path = run_dir / f"story_{story_model}.json"
    with story_json_path.open("w", encoding="utf-8") as file:
        file.write(story.model_dump_json(indent=4))
    return story_json_path


def write_quiz_json(story_id: str, quiz: Any, quiz_model: str) -> Path:
    run_dir = get_run_dir(story_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    quiz_json_path = run_dir / f"quiz_{quiz_model}.json"
    with quiz_json_path.open("w", encoding="utf-8") as file:
        file.write(quiz.model_dump_json(indent=4))
    return quiz_json_path


def find_story_json_path(story_id: str) -> Path | None:
    run_dir = get_run_dir(story_id)
    if not run_dir.is_dir():
        return None

    story_files = sorted(run_dir.glob(STORY_GLOB))
    if not story_files:
        return None
    return story_files[0]


def find_quiz_json_path(story_id: str) -> Path | None:
    run_dir = get_run_dir(story_id)
    if not run_dir.is_dir():
        return None

    quiz_files = sorted(run_dir.glob(QUIZ_GLOB))
    if not quiz_files:
        return None
    return quiz_files[0]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _normalize_url_prefix(prefix: str | None) -> str:
    if prefix is None:
        prefix = get_settings().static_outputs_prefix

    normalized = str(prefix).strip()
    if not normalized or normalized == "/":
        return ""
    return normalized.rstrip("/")


def build_outputs_url(relative_path: str | Path, prefix: str | None = None) -> str:
    rel_path = Path(relative_path).as_posix().lstrip("/")
    normalized_prefix = _normalize_url_prefix(prefix)
    if normalized_prefix:
        return f"{normalized_prefix}/{rel_path}"
    return f"/{rel_path}"


def to_outputs_url(path: Path, prefix: str | None = None) -> str | None:
    outputs_dir = ensure_outputs_dir().resolve()
    try:
        rel_path = path.resolve().relative_to(outputs_dir)
    except Exception:
        return None
    return build_outputs_url(rel_path, prefix=prefix)


def to_static_outputs_url(path: Path) -> str | None:
    return to_outputs_url(path)


def resolve_manifest_asset_path(run_dir: Path, raw_path: str) -> Path | None:
    normalized = (raw_path or "").strip().replace("\\", "/")
    if not normalized:
        return None

    candidate = Path(normalized)
    outputs_dir = ensure_outputs_dir()
    candidates: list[Path] = []

    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        candidates.append(run_dir / candidate)
        candidates.append(outputs_dir / candidate)
        if candidate.parts and candidate.parts[0] == outputs_dir.name:
            candidates.append(outputs_dir.parent / candidate)

    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None
