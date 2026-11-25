import sqlite3
from dataclasses import replace

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient

from app import settings
from app.main import create_app
from app.migrations import init_db
from app.repo import create_application, create_job
from app.automation.playwright_runner import run_playwright
from app.routes.applications import applications_start


def test_empty_launch_migrates_and_respects_local_browser_boundary(tmp_path, monkeypatch):
    db = tmp_path / "db" / "autoapply.db"
    monkeypatch.setattr(settings, "_SETTINGS", replace(settings.get_settings(), database_path=str(db)))
    with TestClient(create_app(), base_url="http://localhost:8000") as client:
        assert client.get("/v1/jobs").json() == []
        assert client.get("/v1/applications/history/recent").json() == []
        assert client.get("/health", headers={"Host": "untrusted.example"}).status_code == 400
        assert client.patch("/v1/settings", headers={"Origin": "https://untrusted.example"},
                            json={"daily_limit": 2}).status_code == 403
        response = client.post("/v1/applications", json={
            "job_id": "fake", "platform": "greenhouse", "mode": "auto"
        })
        assert response.status_code == 400
    init_db(db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 3


def test_legacy_auto_cannot_open_a_browser(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite"
    init_db(db)
    monkeypatch.setattr(settings, "_SETTINGS", replace(settings.get_settings(), database_path=str(db)))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        job = create_job(conn, {"source": "manual", "title": "Example", "company": "Example",
                                "url": "https://example.org/jobs/123", "status": "new"})
        app = create_application(conn, job["id"], "greenhouse", "auto")
    with pytest.raises(HTTPException, match="Legacy auto runs"):
        applications_start(app["id"], BackgroundTasks())
    # Must return before consulting the database or importing/launching Playwright.
    assert run_playwright(None, app, job) == {"status": "manual_only"}


def test_invalid_migration_rolls_back_its_schema_and_marker(tmp_path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    broken = tmp_path / "004_bad.sql"
    broken.write_text("CREATE TABLE broken(id INTEGER);\nTHIS IS NOT SQL;\n")
    with pytest.raises(sqlite3.OperationalError):
        init_db(db, [broken])
    with sqlite3.connect(db) as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='broken'").fetchone()
        assert not conn.execute("SELECT 1 FROM schema_migrations WHERE filename=?", (broken.name,)).fetchone()


def test_drafts_use_configured_resume_without_seeding(tmp_path, monkeypatch):
    from app.ai import AIError, AIResult
    from app.routes import jobs

    db = tmp_path / "test.db"
    init_db(db)
    resume = tmp_path / "resume.md"
    resume.write_text("Synthetic candidate with Python experience.", encoding="utf-8")
    monkeypatch.setattr(settings, "_SETTINGS", replace(settings.get_settings(),
                                                    database_path=str(db), profile_base_resume_path=str(resume)))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        job = create_job(conn, {"source": "manual", "title": "Developer", "company": "Example",
                                "url": "https://example.org/jobs/123", "status": "new"})
    def model(base, *args):
        assert base == resume.read_text()
        return AIResult({"resume": "Draft résumé", "cover_letter": "Draft letter"}, "fake-model", "hash")

    monkeypatch.setattr(jobs, "tailor_resume", model)
    monkeypatch.setattr(jobs, "generate_cover_letter", model)
    draft = jobs._draft(job["id"], "resume_tailored", None)
    letter = jobs._draft(job["id"], "cover_letter", None)
    assert draft["resume_version_id"] == letter["resume_version_id"]
    assert letter["content_text"] == "Draft letter"

    def offline(*args):
        raise AIError("Ollama offline")

    monkeypatch.setattr(jobs, "tailor_resume", offline)
    with pytest.raises(HTTPException, match="did not return a draft") as error:
        jobs._draft(job["id"], "resume_tailored", None)
    assert error.value.status_code == 503
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM generated_content").fetchone()[0] == 2


def test_private_workspace_exposes_only_matched_baselines(tmp_path, monkeypatch):
    from app.cv_workspace import draft_protocol, list_baselines, pick_baseline
    from app.routes import jobs, profile

    base = tmp_path / "workspace" / "baselines"
    base.mkdir(parents=True)
    (base / "data-analyst.txt").write_text("Fictional candidate")
    pdf = base / "data-analyst.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% Fictional fixture")
    (base / "pdf-only.pdf").write_bytes(b"%PDF-1.4")
    outside = tmp_path / "private.txt"
    outside.write_text("Do not expose")
    (base / "escaped.txt").symlink_to(outside)
    guides = base.parent / "protocols"
    guides.mkdir()
    (guides / "DRAFTING.md").write_text("Use only verified evidence.")
    config = replace(settings.get_settings(), cv_workspace=str(base.parent),
                     ollama_base_url="https://external.example")
    monkeypatch.setattr(settings, "_SETTINGS", config)
    assert list_baselines() == [{"id": "data-analyst", "label": "Data Analyst"}]
    assert pick_baseline("data-analyst", ".txt") == base / "data-analyst.txt"
    assert pick_baseline("../private", ".txt") is None
    assert pick_baseline("escaped", ".txt") is None
    assert draft_protocol() == "Use only verified evidence."
    assert profile.cv_workspace_preview("data-analyst").path == pdf
    with pytest.raises(HTTPException, match="requires Ollama on this computer"):
        jobs._draft("not-used", "resume_tailored", None, "data-analyst")
