from types import SimpleNamespace

from app.automation import playwright_runner as runner
from app.automation.review_fill import review_evidence


URL = "https://job-boards.greenhouse.io/example/jobs/123"


class Page:
    def __init__(self, url=URL, *, form=True, code=False, receipt=False):
        self.url = url
        self.form = form
        self.code = code
        self.receipt = receipt

    def locator(self, selector):
        if "security-input-0" in selector:
            return SimpleNamespace(count=lambda: 1, is_visible=lambda: self.code)
        return SimpleNamespace(count=lambda: int(self.form))

    def get_by_role(self, *_args, **_kwargs):
        return SimpleNamespace(all=lambda: [SimpleNamespace(is_visible=lambda: self.receipt)])

    def is_closed(self):
        return False

    def wait_for_timeout(self, _ms):
        self.code = False
        self.form = False
        self.url = URL + "/confirmation"
        self.receipt = True


def test_receipt_needs_visible_confirmation_for_the_same_job_and_no_active_form():
    assert review_evidence(Page(receipt=True), URL) is None
    assert review_evidence(Page(URL + "/confirmation", receipt=True), URL) is None
    assert review_evidence(Page(URL + "/confirmation", form=False), URL) is None
    assert review_evidence(Page(URL + "/confirmation", form=False, receipt=True), URL + "4") is None
    assert review_evidence(Page(URL + "/confirmation", form=False, receipt=True), URL) == "confirmed"


def test_email_verification_does_not_count_until_receipt(monkeypatch):
    events = []
    monkeypatch.setattr(runner, "_is_run_cancelled", lambda *_: False)
    monkeypatch.setattr(runner, "set_application_state", lambda _, app, state, event: events.append((app, state, event)))
    page = Page(code=True)
    review = {"attempted": True, "verification": False}
    result = runner._wait_for_interactive_session(None, {"id": "fixture"}, page, 5, URL, review)
    assert result == "confirmed"
    assert events == [("fixture", "submitting", "fill_review_verification")]


def test_attempt_without_receipt_does_not_become_completed(monkeypatch):
    events = []
    monkeypatch.setattr(runner, "_is_run_cancelled", lambda *_: False)
    monkeypatch.setattr(runner, "set_application_state", lambda _, app, state, event: events.append((app, state, event)))
    review = {"attempted": True, "verification": False}
    result = runner._wait_for_interactive_session(None, {"id": "fixture"}, Page(), 0, URL, review)
    assert result == "timeout"
    assert events == [("fixture", "submitting", "fill_review_submission_pending")]


def test_existing_receipt_or_unknown_blocks_other_runs(monkeypatch):
    from contextlib import nullcontext
    from pathlib import Path
    import sqlite3
    import pytest
    from fastapi import BackgroundTasks, HTTPException
    from app.repo import create_application, create_job
    from app.routes import applications

    db = sqlite3.connect(":memory:", isolation_level=None)
    db.row_factory = sqlite3.Row
    db.executescript((Path(__file__).resolve().parents[1] / "migrations/001_init.sql").read_text())
    job = create_job(db, {"source": "manual", "title": "Test role", "company": "Synthetic",
                          "url": URL, "status": "new"})
    first = create_application(db, job["id"], "greenhouse", "fill_review")
    second = create_application(db, job["id"], "greenhouse", "fill_review")
    db.execute("UPDATE applications SET started_at = '2020-01-01' WHERE id = ?", (second["id"],))
    monkeypatch.setattr(applications, "db_conn", lambda: nullcontext(db))
    for state in ("submitting", "completed"):
        db.execute("UPDATE applications SET state = ? WHERE id = ?", (state, first["id"]))
        with pytest.raises(HTTPException, match="already open") as exc:
            applications.applications_start(second["id"], BackgroundTasks())
        assert exc.value.status_code == 409
    with pytest.raises(HTTPException, match="matching employer receipt"):
        applications.applications_complete(second["id"])
