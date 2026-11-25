import asyncio
import httpx

from app.main import create_app


def test_health() -> None:
    async def _run():
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    asyncio.run(_run())


def test_recent_history_endpoint(tmp_path, monkeypatch) -> None:
    from dataclasses import replace
    from app import settings
    from app.migrations import init_db

    db = tmp_path / "test.db"
    init_db(db)
    monkeypatch.setattr(settings, "_SETTINGS", replace(settings.get_settings(), database_path=str(db)))

    async def _run():
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            resp = await client.get("/v1/applications/history/recent?limit=5")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    asyncio.run(_run())


def test_transition_validation() -> None:
    from app.repo import validate_transition

    assert validate_transition("pending", "filling_form") is True
    assert validate_transition("pending", "completed") is False
    assert validate_transition("submitting", "completed") is True
    assert validate_transition("failed", "pending") is False
