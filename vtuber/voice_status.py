"""Read-only local health probe; no text, tokens, synthesis or remote URLs."""
import httpx


async def local_voice_status():
    try:
        async with httpx.AsyncClient(timeout=1.5, trust_env=False, follow_redirects=False) as client:
            response = await client.get("http://127.0.0.1:12394/health")
            response.raise_for_status()
            data = response.json()
        if data.get("service") != "moonbell-local-voice":
            return {"state": "unavailable"}
        if data.get("ready") is not True:
            return {"state": "loading"}
        return {"state": "ready" if data.get("available") is True else "busy"}
    except (httpx.HTTPError, ValueError):
        return {"state": "unavailable"}
