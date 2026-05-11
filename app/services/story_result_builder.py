from __future__ import annotations

from pathlib import Path
from typing import Any

from app.schemas.story import AssetStatus
from app.services.output_paths import (
    build_outputs_url,
    ensure_outputs_dir,
    find_quiz_json_path,
    find_story_json_path,
    get_run_dir,
    load_json,
    slugify,
    slugify_language_name,
    to_outputs_url,
)
from app.services.result_manifests import (
    find_manifest_asset_url,
    load_audio_manifest,
    load_illustration_manifest,
    load_vocabulary_manifest,
)


def _default_asset_summary(
    enabled: bool,
    total_tasks: int,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "total_tasks": total_tasks if enabled else 0,
        "generated": 0,
        "skipped": 0,
        "failed": 0,
        "aspect_ratio": aspect_ratio if enabled else None,
        "manifest_url": None,
        "service_error": None,
    }


def default_critic_summary(enabled: bool = False) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "attempts": 0,
        "final_verdict": None,
        "issue_count": 0,
        "results": [],
    }


def _derive_asset_summary_from_statuses(
    statuses: list[AssetStatus],
    enabled: bool,
    manifest_url: str | None = None,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    if not enabled:
        return _default_asset_summary(enabled=False, total_tasks=0, aspect_ratio=None)

    generated = 0
    skipped = 0
    failed = 0
    for status in statuses:
        if status == "generated":
            generated += 1
        elif status in {"skipped_exists", "skipped_empty_text"}:
            skipped += 1
        elif status in {"failed", "missing"}:
            failed += 1

    return {
        "enabled": True,
        "total_tasks": len(statuses),
        "generated": generated,
        "skipped": skipped,
        "failed": failed,
        "aspect_ratio": aspect_ratio,
        "manifest_url": manifest_url,
        "service_error": None,
    }


def _first_existing_illustration_url(
    run_dir: Path,
    page_number: int,
    static_prefix: str | None = None,
) -> str | None:
    illustrations_dir = run_dir / "illustrations"
    if not illustrations_dir.is_dir():
        return None
    for file_path in sorted(illustrations_dir.glob(f"page_{page_number:02d}.*")):
        if file_path.is_file() and file_path.stat().st_size > 0:
            return to_outputs_url(file_path, prefix=static_prefix)
    return None


def _first_existing_cover_url(run_dir: Path, static_prefix: str | None = None) -> str | None:
    illustrations_dir = run_dir / "illustrations"
    if not illustrations_dir.is_dir():
        return None
    for file_path in sorted(illustrations_dir.glob("cover.*")):
        if file_path.is_file() and file_path.stat().st_size > 0:
            return to_outputs_url(file_path, prefix=static_prefix)
    return None


def _normalize_vocabulary_entry_id(raw_entry: dict[str, Any], index: int) -> str:
    raw_id = slugify(str(raw_entry.get("entry_id", "")).strip())
    if raw_id:
        return raw_id

    primary_word = slugify(str(raw_entry.get("primary_word", "")).strip())
    if primary_word:
        return primary_word

    secondary_word = slugify(str(raw_entry.get("secondary_word", "")).strip())
    if secondary_word:
        return secondary_word

    return f"word-{index:02d}"


def _build_vocabulary_payload(
    *,
    story_id: str,
    run_dir: Path,
    outputs_dir: Path,
    static_prefix: str | None,
    page_number: int,
    raw_entries: Any,
    vocabulary_entry_map: dict[tuple[int, str, str], dict[str, Any]],
    vocabulary_manifest_exists: bool,
) -> list[dict[str, Any]]:
    if not isinstance(raw_entries, list):
        return []

    payload_entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_entry in enumerate(raw_entries, start=1):
        if not isinstance(raw_entry, dict):
            continue

        base_entry_id = _normalize_vocabulary_entry_id(raw_entry=raw_entry, index=index)
        entry_id = base_entry_id
        suffix = 2
        while entry_id in seen_ids:
            entry_id = f"{base_entry_id}-{suffix}"
            suffix += 1
        seen_ids.add(entry_id)

        primary_rel = (
            Path(story_id)
            / "vocabulary"
            / f"page_{page_number:02d}"
            / f"{entry_id}_primary.wav"
        )
        secondary_rel = (
            Path(story_id)
            / "vocabulary"
            / f"page_{page_number:02d}"
            / f"{entry_id}_secondary.wav"
        )
        primary_file = outputs_dir / primary_rel
        secondary_file = outputs_dir / secondary_rel

        has_primary_audio = primary_file.exists() and primary_file.is_file()
        has_secondary_audio = secondary_file.exists() and secondary_file.is_file()

        primary_manifest_entry = vocabulary_entry_map.get((page_number, entry_id, "primary"))
        secondary_manifest_entry = vocabulary_entry_map.get((page_number, entry_id, "secondary"))

        if primary_manifest_entry is not None:
            primary_status = primary_manifest_entry["status"]
            primary_error = primary_manifest_entry.get("error")
            primary_url = find_manifest_asset_url(
                run_dir=run_dir,
                entry=primary_manifest_entry,
                static_prefix=static_prefix,
            )
            if primary_url is None and has_primary_audio:
                primary_url = build_outputs_url(primary_rel, prefix=static_prefix)
        elif has_primary_audio:
            primary_status = "generated"
            primary_error = None
            primary_url = build_outputs_url(primary_rel, prefix=static_prefix)
        else:
            primary_status = "missing" if vocabulary_manifest_exists else "not_requested"
            primary_error = None
            primary_url = None

        if secondary_manifest_entry is not None:
            secondary_status = secondary_manifest_entry["status"]
            secondary_error = secondary_manifest_entry.get("error")
            secondary_url = find_manifest_asset_url(
                run_dir=run_dir,
                entry=secondary_manifest_entry,
                static_prefix=static_prefix,
            )
            if secondary_url is None and has_secondary_audio:
                secondary_url = build_outputs_url(secondary_rel, prefix=static_prefix)
        elif has_secondary_audio:
            secondary_status = "generated"
            secondary_error = None
            secondary_url = build_outputs_url(secondary_rel, prefix=static_prefix)
        else:
            secondary_status = "missing" if vocabulary_manifest_exists else "not_requested"
            secondary_error = None
            secondary_url = None

        payload_entries.append(
            {
                "entry_id": entry_id,
                "primary_word": str(raw_entry.get("primary_word", "")),
                "secondary_word": str(raw_entry.get("secondary_word", "")),
                "primary_definition": str(raw_entry.get("primary_definition", "")),
                "secondary_definition": str(raw_entry.get("secondary_definition", "")),
                "pronunciation": {
                    "primary_url": primary_url,
                    "secondary_url": secondary_url,
                    "primary_status": primary_status,
                    "primary_error": primary_error,
                    "secondary_status": secondary_status,
                    "secondary_error": secondary_error,
                    "has_primary_audio": has_primary_audio,
                    "has_secondary_audio": has_secondary_audio,
                },
            }
        )

    return payload_entries


def build_story_result_payload(
    story_id: str,
    include_tts: bool,
    include_illustration: bool,
    include_cover_illustration: bool,
    illustration_aspect_ratio: str,
    cover_aspect_ratio: str,
    job_status: str,
    service_errors: dict[str, str | None] | None = None,
    critic: dict[str, Any] | None = None,
    static_prefix: str | None = None,
) -> dict[str, Any]:
    run_dir = get_run_dir(story_id)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run not found: {story_id}")

    story_json_path = find_story_json_path(story_id)
    if story_json_path is None:
        raise FileNotFoundError(f"story json not found for run: {story_id}")

    story_json_url = to_outputs_url(story_json_path, prefix=static_prefix)
    quiz_json_path = find_quiz_json_path(story_id)
    quiz_json_url = (
        to_outputs_url(quiz_json_path, prefix=static_prefix)
        if quiz_json_path is not None
        else None
    )
    story = load_json(story_json_path)
    pages = story.get("pages")
    if not isinstance(pages, list):
        raise ValueError("story json is missing a valid 'pages' list")

    outputs_dir = ensure_outputs_dir()
    primary_language = str(story.get("primary_language", ""))
    secondary_language = str(story.get("secondary_language", ""))
    primary_slug = slugify_language_name(primary_language)
    secondary_slug = slugify_language_name(secondary_language)

    audio_entry_map, audio_manifest_summary, audio_manifest_url = load_audio_manifest(
        run_dir,
        static_prefix=static_prefix,
    )
    (
        illustration_entry_map,
        cover_manifest_entry,
        illustration_manifest_summary,
        illustration_manifest_url,
    ) = load_illustration_manifest(run_dir, static_prefix=static_prefix)
    vocabulary_entry_map, vocabulary_manifest_exists = load_vocabulary_manifest(run_dir)

    tts_statuses: list[AssetStatus] = []
    illustration_statuses: list[AssetStatus] = []

    payload_pages: list[dict[str, Any]] = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            continue

        raw_page_number = page.get("page_number", index + 1)
        try:
            page_number = int(raw_page_number)
        except (TypeError, ValueError):
            page_number = index + 1

        primary_rel = (
            Path(story_id) / "audio" / f"01_{primary_slug}" / f"page_{page_number:02d}_primary.wav"
        )
        secondary_rel = (
            Path(story_id) / "audio" / f"02_{secondary_slug}" / f"page_{page_number:02d}_secondary.wav"
        )
        primary_file = outputs_dir / primary_rel
        secondary_file = outputs_dir / secondary_rel

        has_primary_audio = primary_file.exists() and primary_file.is_file()
        has_secondary_audio = secondary_file.exists() and secondary_file.is_file()

        primary_manifest_entry = audio_entry_map.get((page_number, "primary"))
        secondary_manifest_entry = audio_entry_map.get((page_number, "secondary"))

        if not include_tts:
            primary_status: AssetStatus = "not_requested"
            secondary_status: AssetStatus = "not_requested"
            primary_error: str | None = None
            secondary_error: str | None = None
        else:
            if primary_manifest_entry is not None:
                primary_status = primary_manifest_entry["status"]
                primary_error = primary_manifest_entry.get("error")
            elif has_primary_audio:
                primary_status = "generated"
                primary_error = None
            else:
                primary_status = "missing"
                primary_error = None

            if secondary_manifest_entry is not None:
                secondary_status = secondary_manifest_entry["status"]
                secondary_error = secondary_manifest_entry.get("error")
            elif has_secondary_audio:
                secondary_status = "generated"
                secondary_error = None
            else:
                secondary_status = "missing"
                secondary_error = None

        tts_statuses.extend([primary_status, secondary_status])

        illustration_entry = illustration_entry_map.get(page_number)
        if not include_illustration:
            illustration_status: AssetStatus = "not_requested"
            illustration_error: str | None = None
            illustration_url = None
        else:
            illustration_url = None
            if illustration_entry is not None:
                illustration_status = illustration_entry["status"]
                illustration_error = illustration_entry.get("error")
                illustration_url = find_manifest_asset_url(
                    run_dir,
                    illustration_entry,
                    static_prefix=static_prefix,
                )
            else:
                illustration_url = _first_existing_illustration_url(
                    run_dir,
                    page_number,
                    static_prefix=static_prefix,
                )
                if illustration_url:
                    illustration_status = "generated"
                    illustration_error = None
                else:
                    illustration_status = "missing"
                    illustration_error = None

        illustration_statuses.append(illustration_status)
        vocabulary_payload = _build_vocabulary_payload(
            story_id=story_id,
            run_dir=run_dir,
            outputs_dir=outputs_dir,
            static_prefix=static_prefix,
            page_number=page_number,
            raw_entries=page.get("vocabulary", []),
            vocabulary_entry_map=vocabulary_entry_map,
            vocabulary_manifest_exists=vocabulary_manifest_exists,
        )

        payload_pages.append(
            {
                "page_number": page_number,
                "text_primary": str(page.get("text_primary", "")),
                "text_secondary": str(page.get("text_secondary", "")),
                "audio_primary_url": (
                    build_outputs_url(primary_rel, prefix=static_prefix)
                    if has_primary_audio
                    else None
                ),
                "audio_secondary_url": (
                    build_outputs_url(secondary_rel, prefix=static_prefix)
                    if has_secondary_audio
                    else None
                ),
                "illustration_url": illustration_url,
                "audio_primary_status": primary_status,
                "audio_primary_error": primary_error,
                "audio_secondary_status": secondary_status,
                "audio_secondary_error": secondary_error,
                "illustration_status": illustration_status,
                "illustration_error": illustration_error,
                "has_primary_audio": has_primary_audio,
                "has_secondary_audio": has_secondary_audio,
                "has_illustration": bool(illustration_url),
                "illustration_prompt": str(page.get("illustration_prompt", "")),
                "illustration_scene_prompt": str(page.get("illustration_scene_prompt", "")),
                "vocabulary": vocabulary_payload,
            }
        )

    tts_summary = _default_asset_summary(
        enabled=include_tts,
        total_tasks=len(tts_statuses),
        aspect_ratio=None,
    )
    if include_tts:
        if audio_manifest_summary is not None:
            tts_summary.update(audio_manifest_summary)
            tts_summary["enabled"] = True
            tts_summary["manifest_url"] = audio_manifest_url
            missing_tts_count = sum(1 for status in tts_statuses if status == "missing")
            if missing_tts_count > 0:
                tts_summary["failed"] = int(tts_summary["failed"]) + missing_tts_count
                if int(tts_summary["total_tasks"]) < len(tts_statuses):
                    tts_summary["total_tasks"] = len(tts_statuses)
        else:
            tts_summary = _derive_asset_summary_from_statuses(
                statuses=tts_statuses,
                enabled=True,
                manifest_url=audio_manifest_url,
                aspect_ratio=None,
            )

    illustration_summary = _default_asset_summary(
        enabled=include_illustration,
        total_tasks=len(illustration_statuses),
        aspect_ratio=illustration_aspect_ratio,
    )
    if include_illustration:
        illustration_summary = _derive_asset_summary_from_statuses(
            statuses=illustration_statuses,
            enabled=True,
            manifest_url=illustration_manifest_url,
            aspect_ratio=illustration_aspect_ratio,
        )
        if illustration_manifest_summary is not None:
            illustration_summary["manifest_url"] = illustration_manifest_url

    cover_enabled = include_illustration and include_cover_illustration
    if not cover_enabled:
        cover_status: AssetStatus = "not_requested"
        cover_error: str | None = None
        cover_url = None
        cover_prompt = ""
    else:
        cover_prompt = str(story.get("cover_illustration_prompt", ""))
        cover_url = None
        if cover_manifest_entry is not None:
            cover_status = cover_manifest_entry["status"]
            cover_error = cover_manifest_entry.get("error")
            cover_url = find_manifest_asset_url(
                run_dir,
                cover_manifest_entry,
                static_prefix=static_prefix,
            )
        else:
            cover_url = _first_existing_cover_url(run_dir, static_prefix=static_prefix)
            if cover_url:
                cover_status = "generated"
                cover_error = None
            else:
                cover_status = "missing"
                cover_error = None

    quiz_service_error = (service_errors or {}).get("quiz")
    tts_service_error = (service_errors or {}).get("tts")
    illustration_service_error = (service_errors or {}).get("illustrations")
    tts_summary["service_error"] = tts_service_error
    illustration_summary["service_error"] = illustration_service_error
    cover_summary = {
        "enabled": cover_enabled,
        "url": cover_url,
        "status": cover_status,
        "error": cover_error,
        "prompt": cover_prompt,
        "aspect_ratio": cover_aspect_ratio,
        "has_cover": bool(cover_url),
    }

    has_partial_failures = bool(
        quiz_service_error
        or (include_tts and (tts_summary["failed"] > 0 or tts_service_error))
        or (
            include_illustration
            and (illustration_summary["failed"] > 0 or illustration_service_error)
        )
        or (cover_enabled and cover_summary["status"] in {"failed", "missing"})
    )

    return {
        "id": story_id,
        "status": job_status,
        "story_json_url": story_json_url,
        "quiz_json_url": quiz_json_url,
        "assets": {
            "tts": tts_summary,
            "illustrations": illustration_summary,
            "cover": cover_summary,
            "has_partial_failures": has_partial_failures,
        },
        "critic": critic if isinstance(critic, dict) else default_critic_summary(),
        "meta": {
            "title_primary": str(story.get("title_primary", "")),
            "title_secondary": str(story.get("title_secondary", "")),
            "primary_language": primary_language,
            "secondary_language": secondary_language,
            "page_count": len(payload_pages),
        },
        "pages": payload_pages,
    }
