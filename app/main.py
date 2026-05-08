from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.stories import router as stories_router
from app.core.auth import build_error
from app.core.config import get_settings
from app.services.request_context import (
    generate_request_id,
    get_request_id,
    log_event,
    reset_request_id,
    set_request_id,
)
from app.services.story_orchestrator import recover_interrupted_jobs


def _json_safe_validation_errors(errors: Any) -> Any:
    return jsonable_encoder(
        errors,
        custom_encoder={
            BaseException: lambda value: str(value),
        },
    )


@asynccontextmanager
async def _lifespan(_: FastAPI):
    recover_interrupted_jobs()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO)

    application = FastAPI(
        title="MoreTale FastAPI",
        version="0.1.0",
        lifespan=_lifespan,
    )
    application.mount(
        settings.static_outputs_prefix,
        StaticFiles(directory=str(settings.outputs_dir)),
        name="outputs",
    )
    application.include_router(stories_router)

    @application.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next,
    ) -> Response:
        request_id = (request.headers.get("X-Request-ID") or "").strip() or generate_request_id()
        request.state.request_id = request_id
        token = set_request_id(request_id)
        start = time.perf_counter()

        log_event(
            event="request.start",
            path=request.url.path,
            method=request.method,
        )

        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            status_code = response.status_code if response is not None else 500
            if response is not None:
                response.headers["X-Request-ID"] = request_id

            log_event(
                event="request.end",
                path=request.url.path,
                method=request.method,
                status_code=status_code,
                latency_ms=latency_ms,
            )
            reset_request_id(token)

    @application.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @application.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            payload: dict[str, Any] = detail
        else:
            payload = build_error(
                code=f"HTTP_{exc.status_code}",
                message=str(detail),
            )
        request_id = get_request_id()
        headers = {"X-Request-ID": request_id} if request_id else None
        return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        safe_errors = _json_safe_validation_errors(exc.errors())
        return JSONResponse(
            status_code=422,
            content=build_error(
                code="VALIDATION_ERROR",
                message="request validation failed",
                detail={"errors": safe_errors},
            ),
            headers={"X-Request-ID": request.state.request_id}
            if hasattr(request.state, "request_id")
            else None,
        )

    @application.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=build_error(
                code="INTERNAL_SERVER_ERROR",
                message="internal server error",
                detail={"reason": str(exc)},
            ),
            headers={"X-Request-ID": request.state.request_id}
            if hasattr(request.state, "request_id")
            else None,
        )

    return application


app = create_app()
