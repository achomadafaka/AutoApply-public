"""Browser-assisted review; only the applicant can submit."""
from __future__ import annotations

import json
import time
from tempfile import NamedTemporaryFile
from pathlib import Path
from typing import Any

from ..cv_workspace import pick_baseline
from ..repo import set_application_state
from ..settings import get_settings
from .review_fill import FORM as REVIEW_FORM
from .review_fill import allowed_target, fill_form, inspect_form, review_evidence


class PlaywrightUnavailable(RuntimeError):
    pass


def _is_run_cancelled(conn, app_id: str) -> bool:
    row = conn.execute(
        "SELECT state, last_error FROM applications WHERE id = ?",
        (app_id,),
    ).fetchone()
    if not row:
        return True
    state = row["state"]
    last_error = row["last_error"]
    if state in {"failed", "completed"}:
        return True
    if last_error == "cancelled":
        return True
    return False


def run_playwright(conn, application: dict[str, Any], job: dict[str, Any] | None) -> dict[str, Any]:
    if application.get("mode") != "fill_review":
        return {"status": "manual_only"}
    if _is_run_cancelled(conn, application["id"]):
        return {"status": "cancelled"}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PlaywrightUnavailable("Install the Playwright optional dependencies.") from exc
    return _run_fill_review(conn, application, (job or {}).get("url"), sync_playwright)


def _run_fill_review(conn, application, target_url, sync_playwright):
    app_id = application["id"]
    if application.get("platform") != "greenhouse" or not allowed_target(target_url):
        return {"status": "unsupported_url"}

    settings = get_settings()
    profile = {key: getattr(settings, f"profile_{key}") for key in (
        "first_name", "last_name", "email", "phone", "linkedin", "github", "website", "location"
    )}
    if not all(profile[key] for key in ("first_name", "last_name", "email")):
        return {"status": "missing_profile"}

    workspace_id = application.get("workspace_resume_id")
    if workspace_id and not pick_baseline(workspace_id, ".pdf"):
        return {"status": "resume_unavailable"}

    if application.get("contact_only"):
        keys = ("first_name", "last_name", "email")
        if application.get("include_phone"):
            keys += ("phone",)
        profile = {key: profile[key] for key in keys}

    # A fresh headed context leaves the actual form available for manual review.
    # This branch has no call to the submission function and never uses the global autosubmit toggle.
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page(service_workers="block")
        try:
            response = page.goto(target_url, wait_until="load", timeout=30_000)
            if not response or not response.ok or not allowed_target(page.url):
                return {"status": "unavailable_listing"}

            form_frame = page.main_frame
            form = page.locator(REVIEW_FORM).first
            try:
                form.wait_for(state="visible", timeout=10_000)
            except Exception:
                # Hosted Greenhouse forms can also appear inside an official same-provider frame.
                frame = next((frame for frame in page.frames if allowed_target(frame.url)
                              and frame.locator(REVIEW_FORM).count()), None)
                if frame is None:
                    return {"status": "no_form"}
                form_frame = frame
                form = frame.locator(REVIEW_FORM).first

            if form.get_attribute("id") == "application-form" and page.locator("form#application-form").count():
                # Modern Greenhouse initially shows a server-rendered shell. Filling it before
                # React takes ownership can be lost on hydration.
                try:
                    page.wait_for_function(
                        """() => {
                          const field = document.querySelector('form#application-form #first_name');
                          return field && Object.keys(field).some(key => key.startsWith('__reactFiber$'));
                        }""",
                        timeout=10_000,
                    )
                except Exception:
                    return {"status": "form_not_ready"}
            if _is_run_cancelled(conn, app_id):
                return {"status": "cancelled"}
            start_urls = page.url, form_frame.url
            review = {"attempted": False, "verification": False}

            def note_submit(source):
                if source["frame"] == form_frame and allowed_target(source["frame"].url):
                    review["attempted"] = True

            page.expose_binding("__autoapplyNoteUserSubmit", note_submit)
            user_active = False

            def note_interaction(source):
                nonlocal user_active
                if source["frame"] == form_frame and (page.url, form_frame.url) == start_urls:
                    user_active = True

            def guard_request(route):
                if user_active:
                    route.fallback()
                else:
                    route.abort("blockedbyclient")

            page.expose_binding("__autoapplyNoteInteraction", note_interaction)
            page.context.route("**/*", guard_request)
            form_frame.evaluate(_START_PREFILL_GUARD, REVIEW_FORM)
            result = fill_form(form, profile)
            if (page.url, form_frame.url) != start_urls or not form.is_visible():
                return {"status": "form_changed"}

            def report(snapshot):
                _write_json_artifact(
                    conn, application, {"platform": "greenhouse", "questions": snapshot["blockers"]},
                    "unanswered_questions", artifact_type="unanswered_questions",
                )

            previous = result
            report(result)
            if _is_run_cancelled(conn, app_id):
                return {"status": "cancelled"}
            conn.execute("UPDATE applications SET last_error = ? WHERE id = ?",
                         ("Review the form and attach documents yourself.", app_id))
            set_application_state(conn, app_id, "awaiting_review", "fill_review_needs_input",
                                  details={"filled": result["filled"], "files": 0,
                                           "blockers": len(result["blockers"])})
            form_frame.evaluate("() => window.__autoapplyArmHandoff()")

            def refresh():
                nonlocal previous
                if (page.url, form_frame.url) != start_urls or not form.count():
                    return
                snapshot = inspect_form(form, profile)
                if snapshot != previous:
                    report(snapshot)
                    previous = snapshot

            reason = _wait_for_interactive_session(
                conn, application, page, settings.automation_interactive_timeout_sec,
                target_url, review, refresh,
            )
            if reason == "confirmed":
                return {"status": "review_confirmed"}
            if review["attempted"] or review["verification"]:
                return {"status": "review_pending", "reason": reason}
            return {"status": "review_closed", "reason": reason}
        finally:
            browser.close()


def _wait_for_interactive_session(
    conn,
    application: dict[str, Any],
    page,
    timeout_sec: float,
    target_url: str | None = None,
    review: dict[str, bool] | None = None,
    refresh=None,
) -> str:
    start = time.monotonic()
    last_event = None
    while True:
        if _is_run_cancelled(conn, application["id"]):
            return "cancelled"
        try:
            if page.is_closed():
                return "closed"
        except Exception:
            return "closed"
        if target_url and review is not None:
            try:
                evidence = review_evidence(page, target_url)
            except Exception:
                evidence = None
            if evidence == "confirmed" and (review["attempted"] or review["verification"]):
                return "confirmed"
            if evidence == "verification" and review["attempted"]:
                review["verification"] = True
            event = ("fill_review_verification" if review["verification"] else
                     "fill_review_submission_pending" if review["attempted"] else None)
            if event and event != last_event:
                set_application_state(conn, application["id"], "submitting", event)
                last_event = event
            if refresh and not review["attempted"]:
                try:
                    refresh()
                except Exception:
                    pass  # the page can change or close between inspection calls
        if (time.monotonic() - start) >= timeout_sec:
            return "timeout"
        try:
            page.wait_for_timeout(1000)
        except Exception:
            return "closed"


_START_PREFILL_GUARD = """selector => {
    const proto = HTMLFormElement.prototype;
    const methods = ['submit', 'requestSubmit'].map(name =>
      [name, Object.getOwnPropertyDescriptor(proto, name)]);
    const block = event => {
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    window.addEventListener('submit', block, true);
    for (const [name, descriptor] of methods)
      Object.defineProperty(proto, name, {...descriptor, value: () => {}});
    window.__autoapplyArmHandoff = () => {
      const allow = event => {
        if (!event.isTrusted || !event.target.closest(selector)) return;
        window.__autoapplyNoteInteraction();
        window.removeEventListener('pointerdown', allow, true);
        window.removeEventListener('keydown', allow, true);
        window.removeEventListener('click', allow, true);
        for (const [name, descriptor] of methods)
          Object.defineProperty(proto, name, descriptor);
        window.removeEventListener('submit', block, true);
        window.addEventListener('submit', event => {
          if (event.isTrusted && event.target.matches(selector)) window.__autoapplyNoteUserSubmit();
        }, {capture: true});
      };
      window.addEventListener('pointerdown', allow, true);
      window.addEventListener('keydown', allow, true);
      window.addEventListener('click', allow, true);
      delete window.__autoapplyArmHandoff;
    };
}"""


def _write_json_artifact(
    conn,
    application: dict[str, Any],
    payload: dict[str, Any],
    suffix: str,
    artifact_type: str = "fields",
):
    out_dir = Path("artifacts/automation")
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = out_dir / f"{application['id']}_{suffix}.json"
    with NamedTemporaryFile(mode="w", dir=out_dir, encoding="utf-8", delete=False) as draft:
        json.dump(payload, draft, indent=2, sort_keys=True)
    Path(draft.name).replace(path)
    artifact_id = f"art_{application['id']}_{suffix}"
    conn.execute(
        """
        INSERT INTO artifacts (id, application_id, type, path, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
          path = excluded.path,
          created_at = excluded.created_at
        """,
        (
            artifact_id,
            application["id"],
            artifact_type,
            str(path),
        ),
    )
