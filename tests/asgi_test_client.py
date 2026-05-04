from __future__ import annotations

from typing import Any

import anyio
import httpx


class ASGITestClient:
    def __init__(self, app: Any, base_url: str = "http://testserver") -> None:
        self.app = app
        self.base_url = base_url

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return anyio.run(self._request, "GET", url, kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return anyio.run(self._request, "POST", url, kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return anyio.run(self._request, "DELETE", url, kwargs)

    async def _request(
        self,
        method: str,
        url: str,
        kwargs: dict[str, Any],
    ) -> httpx.Response:
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url=self.base_url,
        ) as client:
            return await client.request(method, url, **kwargs)
