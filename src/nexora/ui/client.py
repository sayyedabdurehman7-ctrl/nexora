"""UI calls only the existing local service, never a paid provider."""

import httpx


class APIClient:
    async def request(self, method: str, path: str, **kwargs):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10, trust_env=False) as client:
            response = await client.request(method, path, **kwargs)
        if response.is_error:
            raise ValueError(response.json().get("error", {}).get("message", "Request failed"))
        return response.json()
