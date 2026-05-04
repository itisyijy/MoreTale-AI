from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def build_error(code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        error["detail"] = detail
    return {"error": error}


async def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    expected_api_keys = get_settings().api_keys
    if not expected_api_keys:
        raise HTTPException(
            status_code=500,
            detail=build_error(
                code="SERVER_MISCONFIGURED",
                message="MORETALE_API_KEY is not configured",
            ),
        )

    if not api_key or api_key not in expected_api_keys:
        raise HTTPException(
            status_code=401,
            detail=build_error(
                code="UNAUTHORIZED",
                message="invalid or missing api key",
            ),
        )
