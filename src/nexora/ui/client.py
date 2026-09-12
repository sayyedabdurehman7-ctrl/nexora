"""UI calls only the existing local service, never a paid provider."""

import os

import httpx


class APIClient:
    async def request(self, method: str, path: str, **kwargs):
        port = os.getenv("PORT", "8000")
        async with httpx.AsyncClient(
            base_url=os.getenv("NEXORA_API_URL", f"http://127.0.0.1:{port}"), timeout=10, trust_env=False
        ) as client:
            response = await client.request(method, path, **kwargs)
        if response.is_error:
            raise ValueError(response.json().get("error", {}).get("message", "Request failed"))
        return response.json()
