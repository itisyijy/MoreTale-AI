from __future__ import annotations

import concurrent.futures
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable

from app.core.config import Settings
from app.services.storage_backend import get_storage_backend


SERVICE_NAME = "moretale-ai"


class HealthCheckError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def run_health_checks(settings: Settings) -> tuple[int, dict[str, Any]]:
    checks = {
        "apiAuth": _check_api_auth(settings),
        "outputsDir": _check_outputs_dir(settings.outputs_dir),
        "storage": _check_storage_backend(settings),
        "geminiStory": _check_genai_model(
            env_name="GEMINI_STORY_API_KEY",
            model=_first_model(settings.allowed_story_models),
            timeout_sec=settings.healthcheck_timeout_sec,
        ),
        "geminiTts": _check_genai_model(
            env_name="GEMINI_TTS_API_KEY",
            model=_first_model(settings.allowed_tts_models),
            timeout_sec=settings.healthcheck_timeout_sec,
        ),
        "illustration": _check_genai_model(
            env_name="NANO_BANANA_KEY",
            model=_first_model(settings.allowed_illustration_models),
            timeout_sec=settings.healthcheck_timeout_sec,
        ),
    }
    status = "ok" if all(check["status"] == "ok" for check in checks.values()) else "unhealthy"
    payload = {
        "status": status,
        "service": SERVICE_NAME,
        "version": "0.1.0",
        "checks": checks,
    }
    return (200 if status == "ok" else 503), payload


def _check_api_auth(settings: Settings) -> dict[str, Any]:
    if settings.api_keys:
        return {"status": "ok"}
    return _failed("missing_env", "MORETALE_API_KEY is required")


def _check_outputs_dir(outputs_dir: Path) -> dict[str, Any]:
    try:
        outputs_dir.mkdir(parents=True, exist_ok=True)
        temp_path = None
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".health-",
            suffix=".tmp",
            dir=outputs_dir,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write("ok")
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        return {"status": "ok"}
    except Exception as exc:
        return _failed(type(exc).__name__, str(exc))


def _check_storage_backend(settings: Settings) -> dict[str, Any]:
    backend_name = settings.storage_backend
    if backend_name == "local":
        return {"status": "ok", "backend": "local"}
    if backend_name != "gcs":
        return _failed("unsupported_backend", f"unsupported storage backend: {backend_name}")
    if not settings.gcs_bucket:
        return _failed("missing_env", "MORETALE_GCS_BUCKET is required", backend="gcs")

    temp_path = None
    relative_path = f".health/{uuid.uuid4().hex}.txt"
    try:
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".health-storage-",
            suffix=".tmp",
            dir=settings.outputs_dir,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write("ok")
        backend = get_storage_backend()
        backend.upload(temp_path, relative_path)
        backend.delete(relative_path)
        return {"status": "ok", "backend": "gcs", "bucket": settings.gcs_bucket}
    except Exception as exc:
        return _failed(type(exc).__name__, str(exc), backend="gcs")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _check_genai_model(
    *,
    env_name: str,
    model: str,
    timeout_sec: float,
) -> dict[str, Any]:
    api_key = (os.getenv(env_name) or "").strip()
    if not api_key:
        return _failed("missing_env", f"{env_name} is required", model=model)

    try:
        _run_with_timeout(
            lambda: _lookup_genai_model(api_key=api_key, model=model),
            timeout_sec=timeout_sec,
        )
        return {"status": "ok", "model": model}
    except HealthCheckError as exc:
        return _failed(exc.code, str(exc), model=model)
    except Exception as exc:
        return _failed(type(exc).__name__, str(exc), model=model)


def _lookup_genai_model(*, api_key: str, model: str) -> None:
    from google import genai

    client = genai.Client(api_key=api_key)
    try:
        client.models.get(model=model)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def _run_with_timeout(callback: Callable[[], None], *, timeout_sec: float) -> None:
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(callback)
    try:
        future.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise HealthCheckError(
            "timeout",
            f"dependency check exceeded {timeout_sec:g}s timeout",
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _first_model(models: tuple[str, ...]) -> str:
    return models[0] if models else ""


def _failed(
    code: str,
    message: str,
    *,
    model: str | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "failed"}
    if model is not None:
        payload["model"] = model
    if backend is not None:
        payload["backend"] = backend
    payload["error"] = {
        "type": code,
        "message": message,
    }
    return payload
