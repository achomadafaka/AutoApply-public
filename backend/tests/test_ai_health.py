import asyncio
import httpx

from app.routes import ai as ai_routes
from app.main import create_app


def test_ai_health(monkeypatch) -> None:
    monkeypatch.setattr(
        ai_routes,
        "check_ollama",
        lambda: {
            "status": "unavailable",
            "base_url": "http://localhost:11434",
            "analyze_model": "test",
            "generate_model": "test",
            "models": [],
            "error": "stubbed",
        },
    )
    async def _run():
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            resp = await client.get("/v1/ai/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in {"ok", "unavailable"}
        assert "base_url" in data
        assert "analyze_model" in data
        assert "generate_model" in data

    asyncio.run(_run())
