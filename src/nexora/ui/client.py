"""UI calls only the existing local service, never a paid provider."""

import os

import httpx


class APIClient:
    async def request(self, method: str, path: str, **kwargs):
        port = os.getenv("PORT", "8000")
        async with httpx.AsyncClient(
            base_url=os.getenv("NEXORA_API_URL", f"http://127.0.0.1:{port}"),
            timeout=httpx.Timeout(10, connect=2),
            trust_env=False,
        ) as client:
            response = await client.request(method, path, **kwargs)
        if response.is_error:
            try:
                message = response.json().get("error", {}).get("message", "Request failed")
            except ValueError:
                message = "NEXORA could not complete that request. Please try again."
            raise ValueError(message)
        return response.json()

    async def health(self) -> bool:
        try:
            status = await self.request("GET", "/health")
            return status.get("status") == "ok" and bool(status.get("safe_mode"))
        except (httpx.HTTPError, ValueError, TypeError):
            return False
