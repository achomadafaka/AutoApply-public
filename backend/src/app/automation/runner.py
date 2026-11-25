from __future__ import annotations

from typing import Any

from ..repo import log_application_event
from ..settings import get_settings
from .playwright_runner import PlaywrightUnavailable, run_playwright


def run_stub(conn, application: dict[str, Any]) -> dict[str, Any]:
    """
    Placeholder automation runner.
    Logs a stub event so the state machine has an auditable step.
    """
    if application.get("mode") != "fill_review":
        return {"status": "manual_only"}
    settings = get_settings()
    if not settings.automation_enabled:
        log_application_event(
            conn,
            application["id"],
            application["state"],
            "automation_disabled",
            "system",
            {
                "platform": application.get("platform"),
                "mode": application.get("mode"),
                "note": "Automation is disabled. Enable AUTOAPPLY_AUTOMATION_ENABLED to run.",
            },
        )
        return {"status": "disabled"}
    log_application_event(
        conn,
        application["id"],
        application["state"],
        "automation_stub",
        "system",
        {
            "platform": application.get("platform"),
            "mode": application.get("mode"),
            "note": "Automation engine not implemented yet.",
        },
    )
    return {"status": "stubbed"}


def run_automation(conn, application: dict[str, Any], job: dict[str, Any] | None) -> dict[str, Any]:
    if application.get("mode") != "fill_review":
        return {"status": "manual_only"}
    settings = get_settings()
    if not settings.automation_enabled:
        log_application_event(
            conn,
            application["id"],
            application["state"],
            "automation_disabled",
            "system",
            {
                "platform": application.get("platform"),
                "mode": application.get("mode"),
                "note": "Automation is disabled. Enable AUTOAPPLY_AUTOMATION_ENABLED to run.",
            },
        )
        return {"status": "disabled"}

    driver = settings.automation_driver
    if driver == "stub":
        return run_stub(conn, application)

    if driver == "playwright":
        try:
            return run_playwright(conn, application, job)
        except PlaywrightUnavailable as exc:
            log_application_event(
                conn,
                application["id"],
                application["state"],
                "automation_unavailable",
                "system",
                {"error": str(exc), "driver": driver},
            )
            return {"status": "unavailable", "driver": driver}
        except Exception as exc:
            log_application_event(
                conn,
                application["id"],
                application["state"],
                "automation_error",
                "system",
                {"error": type(exc).__name__ if application.get("mode") == "fill_review" else str(exc),
                 "driver": driver},
            )
            return {"status": "error", "driver": driver}

    log_application_event(
        conn,
        application["id"],
        application["state"],
        "automation_invalid_driver",
        "system",
        {"driver": driver},
    )
    return {"status": "invalid_driver", "driver": driver}
