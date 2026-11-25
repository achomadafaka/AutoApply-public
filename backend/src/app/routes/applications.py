from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ..db import db_conn
from ..automation.runner import run_automation
from ..repo import (
    create_application,
    get_application,
    get_recent_history,
    count_applications_started_between,
    get_application_stats,
    list_applications,
    list_application_history,
    list_application_artifacts,
    delete_application,
    set_application_state,
    validate_transition,
)
from ..settings import get_settings
from ..settings_store import load_settings
from ..schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationHistoryOut,
    FillReviewStartIn,
    ApplicationState,
    ApplicationStatsOut,
    Platform,
)


router = APIRouter(tags=["applications"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/applications", response_model=ApplicationOut, status_code=201)
def applications_create(payload: ApplicationCreate):
    if payload.mode.value == "auto":
        raise HTTPException(status_code=400, detail="Automatic submission is not supported. Use Fill & Review.")
    if payload.mode.value == "fill_review" and payload.platform.value != "greenhouse":
        raise HTTPException(status_code=400, detail="Fill & Review supports hosted Greenhouse jobs only.")
    with db_conn() as conn:
        job = conn.execute("SELECT id FROM job_listings WHERE id = ?", (payload.job_id,)).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        data = payload.model_dump(mode="json")
        app = create_application(conn, data["job_id"], data["platform"], data["mode"])
    return app


@router.get("/applications", response_model=list[ApplicationOut])
def applications_list(
    state: ApplicationState | None = Query(default=None),
    platform: Platform | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with db_conn() as conn:
        rows = list_applications(
            conn,
            state.value if state else None,
            platform.value if platform else None,
            limit,
            offset,
        )
    return rows


@router.get("/applications/stats", response_model=ApplicationStatsOut)
def applications_stats():
    with db_conn() as conn:
        stats = get_application_stats(conn)
    pending_review = (
        stats.get("pending", 0)
        + stats.get("awaiting_review", 0)
    )
    in_progress = (
        stats.get("analyzing_job", 0)
        + stats.get("generating_materials", 0)
        + stats.get("filling_form", 0)
        + stats.get("submitting", 0)
    )
    completed = stats.get("completed", 0)
    failed = stats.get("failed", 0)
    total = sum(stats.values())
    return ApplicationStatsOut(
        pending_review=pending_review,
        in_progress=in_progress,
        completed=completed,
        failed=failed,
        total=total,
    )


@router.get("/applications/{app_id}", response_model=ApplicationOut)
def applications_get(app_id: str):
    with db_conn() as conn:
        app = get_application(conn, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.delete("/applications/{app_id}", response_model=ApplicationOut)
def applications_delete(app_id: str):
    artifact_paths: list[str] = []
    with db_conn() as conn:
        app = get_application(conn, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        if app["state"] in {
            "analyzing_job",
            "generating_materials",
            "awaiting_review",
            "filling_form",
            "submitting",
        }:
            raise HTTPException(status_code=409, detail="Cancel run before deleting")
        artifact_paths = [
            row["path"] for row in list_application_artifacts(conn, app_id, None, 200, 0)
        ]
        deleted = delete_application(conn, app_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
    artifact_root = Path("artifacts").resolve()
    for path in artifact_paths:
        try:
            candidate = Path(path).resolve()
            if candidate.is_relative_to(artifact_root) and candidate.is_file():
                candidate.unlink(missing_ok=True)
        except Exception:
            continue
    return deleted


@router.post("/applications/{app_id}/start", response_model=ApplicationOut)
def applications_start(app_id: str, background_tasks: BackgroundTasks, payload: FillReviewStartIn | None = None):
    with db_conn() as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        app = get_application(conn, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        if app["mode"] == "auto":
            raise HTTPException(status_code=409, detail="Legacy auto runs cannot be started. Use Fill & Review.")
        next_state = "filling_form"
        if app["mode"] == "fill_review" and app["state"] == "awaiting_review":
            event = conn.execute(
                "SELECT event FROM application_history WHERE application_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1", (app_id,),
            ).fetchone()
            if event and event["event"] in {"fill_review_ready", "fill_review_needs_input"}:
                raise HTTPException(status_code=409, detail="The review browser is already open.")
        if not validate_transition(app["state"], next_state):
            raise HTTPException(status_code=409, detail="Invalid state transition")
        if not app.get("started_at"):
            settings = get_settings()
            stored = (
                load_settings(settings.settings_path)
                if os.path.exists(settings.settings_path)
                else {}
            )
            start_of_day = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_of_day = start_of_day + timedelta(days=1)
            started_today = count_applications_started_between(
                conn, start_of_day.isoformat(), end_of_day.isoformat()
            )
            daily_limit = stored.get("daily_limit", settings.daily_limit)
            if started_today >= daily_limit:
                raise HTTPException(
                    status_code=429,
                    detail="Daily application limit reached",
                )
        changed = conn.execute(
            "UPDATE applications SET state = ?, last_error = NULL, started_at = COALESCE(started_at, ?) "
            "WHERE id = ? AND state = ? "
            "AND NOT EXISTS (SELECT 1 FROM applications other "
            "JOIN job_listings candidate ON candidate.id = other.job_id "
            "JOIN job_listings requested ON requested.id = applications.job_id "
            "WHERE (other.job_id = applications.job_id OR candidate.url = requested.url) "
            "AND other.id <> applications.id "
            "AND other.state IN ('filling_form', 'awaiting_review', 'submitting', 'completed'))",
            (next_state, _now(), app_id, app["state"]),
        ).rowcount
        if not changed:
            raise HTTPException(
                status_code=409,
                detail="A run for this job is already open, pending confirmation, or completed.",
            )
        updated = set_application_state(conn, app_id, next_state, "started")
        job = conn.execute(
            "SELECT * FROM job_listings WHERE id = ?",
            (updated["job_id"],),
        ).fetchone()
        job_dict = dict(job) if job else None
        if app["mode"] == "fill_review":
            run_input = payload.model_dump() if payload else {}
            background_tasks.add_task(_finish_fill_review, {**updated, **run_input}, job_dict)
    return updated


def _finish_fill_review(application, job):
    with db_conn() as conn:
        app_id = application["id"]
        result = run_automation(conn, application, job)
        status = result["status"]
        current = get_application(conn, app_id)
        if not current or current["state"] in {"failed", "completed"}:
            return
        if status == "review_confirmed":
            conn.execute("UPDATE applications SET completed_at = ?, last_error = NULL WHERE id = ?",
                         (_now(), app_id))
            set_application_state(conn, app_id, "completed", "fill_review_confirmed",
                                  details={"evidence": "visible_same_job_confirmation"})
        elif status == "review_pending" or current["state"] == "submitting":
            conn.execute("UPDATE applications SET last_error = ? WHERE id = ?",
                         ("No receipt confirmed. Check the employer or your inbox before applying again.",
                          app_id))
            set_application_state(conn, app_id, "submitting", "fill_review_pending_closed",
                                  details={"reason": result.get("reason", "interrupted")})
        elif status == "review_closed":
            # A closed browser is not a submission. Keep the run available to reopen.
            conn.execute("UPDATE applications SET last_error = ? WHERE id = ?",
                         ("Browser closed or timed out. Reopen to refill.", app_id))
            set_application_state(conn, app_id, "awaiting_review", "fill_review_closed")
        elif status != "cancelled":
            messages = {
                "unsupported_url": "Fill & Review supports hosted Greenhouse applications only.",
                "no_form": "Could not find the Greenhouse application form. Check the listing.",
                "form_changed": "The form changed during prefill. Reopen it or fill it manually.",
                "form_not_ready": "Greenhouse did not finish loading; reopen the review to retry.",
                "unavailable_listing": "Listing is unavailable or redirected outside Greenhouse.",
                "resume_unavailable": "The selected résumé is no longer available. Choose another before reopening.",
                "missing_profile": "Configure your first name, last name, and email before filling.",
                "disabled": "Browser automation is disabled in settings.",
                "stubbed": "Enable the Playwright automation driver.",
                "unavailable": "Playwright is not installed.",
                "error": "Could not open or fill the form. Check application history.",
            }
            conn.execute("UPDATE applications SET last_error = ? WHERE id = ?",
                         (messages.get(status, "Fill & Review could not run."), app_id))
            set_application_state(conn, app_id, "awaiting_review", "fill_review_blocked",
                                  details={"status": status})



@router.post("/applications/{app_id}/complete", response_model=ApplicationOut)
def applications_complete(app_id: str):
    with db_conn() as conn:
        app = get_application(conn, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        if app["state"] == "completed":
            raise HTTPException(status_code=409, detail="Application already completed")
        if app["mode"] == "fill_review":
            raise HTTPException(status_code=409, detail="Fill & Review needs a matching employer receipt.")
        if app["state"] == "failed":
            raise HTTPException(status_code=409, detail="Cannot complete failed run")
        updated = set_application_state(conn, app_id, "completed", "marked_completed")
        conn.execute(
            "UPDATE applications SET completed_at = ? WHERE id = ?",
            (_now(), app_id),
        )
        updated = get_application(conn, app_id)
    return updated


@router.post("/applications/{app_id}/pause", response_model=ApplicationOut)
def applications_pause(app_id: str):
    with db_conn() as conn:
        app = get_application(conn, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        if app["state"] in {"completed", "failed"}:
            raise HTTPException(status_code=409, detail="Cannot pause completed run")
        set_application_state(conn, app_id, app["state"], "paused")
        updated = get_application(conn, app_id)
    return updated


@router.post("/applications/{app_id}/resume", response_model=ApplicationOut)
def applications_resume(app_id: str):
    with db_conn() as conn:
        app = get_application(conn, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        if app["state"] in {"completed", "failed"}:
            raise HTTPException(status_code=409, detail="Cannot resume completed run")
        set_application_state(conn, app_id, app["state"], "resumed")
        updated = get_application(conn, app_id)
    return updated


@router.post("/applications/{app_id}/cancel", response_model=ApplicationOut)
def applications_cancel(app_id: str):
    with db_conn() as conn:
        app = get_application(conn, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        if app["state"] in {"completed", "failed", "submitting"}:
            raise HTTPException(status_code=409, detail="Cannot cancel a finalized or unconfirmed submission")
        conn.execute(
            "UPDATE applications SET last_error = ?, completed_at = ? WHERE id = ?",
            ("cancelled", _now(), app_id),
        )
        updated = set_application_state(conn, app_id, "failed", "cancelled")
    return updated


@router.get("/applications/{app_id}/history", response_model=list[ApplicationHistoryOut])
def applications_history(app_id: str):
    with db_conn() as conn:
        app = get_application(conn, app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        history = list_application_history(conn, app_id)
    return history


@router.get("/applications/history/recent", response_model=list[ApplicationHistoryOut])
async def applications_recent_history(limit: int = Query(default=10, ge=1, le=50)):
    with db_conn() as conn:
        rows = get_recent_history(conn, limit)
    return rows
