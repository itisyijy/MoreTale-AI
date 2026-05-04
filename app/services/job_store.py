from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.output_paths import get_run_dir

_META_FILE_NAME = "meta.json"
_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    def _meta_path(self, story_id: str) -> Path:
        return get_run_dir(story_id) / _META_FILE_NAME

    def initialize_job(self, story_id: str, request_payload: dict[str, Any]) -> dict[str, Any]:
        run_dir = get_run_dir(story_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        now = _utc_now_iso()
        meta = {
            "id": story_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "request": request_payload,
            "result": None,
            "error": None,
        }
        self._write_meta(self._meta_path(story_id), meta)
        return meta

    def load_job(self, story_id: str) -> dict[str, Any] | None:
        meta_path = self._meta_path(story_id)
        if not meta_path.is_file():
            return None
        with _LOCK:
            with meta_path.open("r", encoding="utf-8") as file:
                return json.load(file)

    def mark_running(self, story_id: str) -> dict[str, Any]:
        return self._set_job_status(story_id=story_id, status="running")

    def mark_completed(self, story_id: str, result: dict[str, Any]) -> dict[str, Any]:
        return self._set_job_status(
            story_id=story_id,
            status="completed",
            result=result,
            error=None,
        )

    def mark_failed(
        self,
        story_id: str,
        error: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._set_job_status(
            story_id=story_id,
            status="failed",
            error=error,
            result=result,
        )

    def mark_canceled(self, story_id: str) -> dict[str, Any]:
        return self._set_job_status(story_id=story_id, status="canceled")

    def _set_job_status(
        self,
        story_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta_path = self._meta_path(story_id)
        if not meta_path.is_file():
            raise FileNotFoundError(f"story meta not found: {story_id}")

        with _LOCK:
            with meta_path.open("r", encoding="utf-8") as file:
                meta = json.load(file)

            meta["status"] = status
            meta["updated_at"] = _utc_now_iso()
            if result is not None:
                meta["result"] = result
            if error is not None:
                meta["error"] = error
            elif status != "failed":
                meta["error"] = None

            self._write_meta(meta_path, meta)
            return meta

    @staticmethod
    def _write_meta(meta_path: Path, meta: dict[str, Any]) -> None:
        temp_path = meta_path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(meta, file, ensure_ascii=False, indent=2)
        temp_path.replace(meta_path)
