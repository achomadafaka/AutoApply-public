from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _row_to_dict(row) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _selector_row_to_dict(row) -> dict[str, Any]:
    data = _row_to_dict(row)
    if not data:
        return data
    selectors_json = data.get("selectors_json") or "[]"
    try:
        data["selectors"] = json.loads(selectors_json)
    except json.JSONDecodeError:
        data["selectors"] = []
    data.pop("selectors_json", None)
    return data


def list_jobs(conn, status: str | None, q: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
    if q:
        rows = conn.execute(
            """
            SELECT jl.*
            FROM job_listings jl
            JOIN job_listings_fts f ON jl.rowid = f.rowid
            WHERE job_listings_fts MATCH ?
            ORDER BY bm25(f)
            LIMIT ? OFFSET ?
            """,
            (q, limit, offset),
        ).fetchall()
    elif status:
        rows = conn.execute(
            "SELECT * FROM job_listings WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM job_listings ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    return [_row_to_dict(r) for r in rows]


def create_job(conn, data: dict[str, Any]) -> dict[str, Any]:
    job_id = _id("job")
    created_at = _now()
    record = {
        "id": job_id,
        "source": data.get("source", "manual"),
        "title": data["title"],
        "company": data["company"],
        "location": data.get("location"),
        "url": data.get("url"),
        "description": data.get("description"),
        "requirements": data.get("requirements"),
        "salary_min": data.get("salary_min"),
        "salary_max": data.get("salary_max"),
        "remote": 1 if data.get("remote") else 0,
        "status": data.get("status", "new"),
        "created_at": created_at,
        "updated_at": created_at,
    }
    conn.execute(
        """
        INSERT INTO job_listings (
          id, source, title, company, location, url, description, requirements,
          salary_min, salary_max, remote, status, created_at, updated_at
        ) VALUES (
          :id, :source, :title, :company, :location, :url, :description, :requirements,
          :salary_min, :salary_max, :remote, :status, :created_at, :updated_at
        )
        """,
        record,
    )
    return record


def get_job(conn, job_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_job_by_url(conn, url: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM job_listings WHERE lower(url) = lower(?)",
        (url,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_job_by_title_company(
    conn,
    title: str,
    company: str,
    location: str | None,
) -> dict[str, Any] | None:
    if location:
        row = conn.execute(
            """
            SELECT * FROM job_listings
            WHERE lower(title) = lower(?)
              AND lower(company) = lower(?)
              AND lower(location) = lower(?)
            """,
            (title, company, location),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT * FROM job_listings
            WHERE lower(title) = lower(?)
              AND lower(company) = lower(?)
              AND (location IS NULL OR trim(location) = '')
            """,
            (title, company),
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete_job(conn, job_id: str) -> dict[str, Any] | None:
    job = get_job(conn, job_id)
    if not job:
        return None
    conn.execute("DELETE FROM job_listings WHERE id = ?", (job_id,))
    return job


def list_artifact_paths_for_job(conn, job_id: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT a.path
        FROM artifacts a
        JOIN applications app ON a.application_id = app.id
        WHERE app.job_id = ?
        """,
        (job_id,),
    ).fetchall()
    return [row["path"] for row in rows]


def update_job(conn, job_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    if not updates:
        return get_job(conn, job_id)

    updates = dict(updates)
    if "remote" in updates and updates["remote"] is not None:
        updates["remote"] = 1 if updates["remote"] else 0
    updates["updated_at"] = _now()

    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    updates["id"] = job_id
    conn.execute(f"UPDATE job_listings SET {set_clause} WHERE id = :id", updates)
    return get_job(conn, job_id)


def create_application(conn, job_id: str, platform: str, mode: str) -> dict[str, Any]:
    app_id = _id("app")
    record = {
        "id": app_id,
        "job_id": job_id,
        "platform": platform,
        "mode": mode,
        "state": "pending",
        "last_error": None,
        "started_at": None,
        "completed_at": None,
    }
    conn.execute(
        """
        INSERT INTO applications (
          id, job_id, platform, mode, state, last_error, started_at, completed_at
        ) VALUES (
          :id, :job_id, :platform, :mode, :state, :last_error, :started_at, :completed_at
        )
        """,
        record,
    )
    _insert_history(conn, app_id, "pending", "created", "system", {"note": "Application created"})
    return record


def get_application(conn, app_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_application(conn, app_id: str) -> dict[str, Any] | None:
    app = get_application(conn, app_id)
    if not app:
        return None
    conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    return app


def list_applications(
    conn,
    state: str | None,
    platform: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    conditions = []
    params: list[Any] = []
    if state:
        conditions.append("state = ?")
        params.append(state)
    if platform:
        conditions.append("platform = ?")
        params.append(platform)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT * FROM applications
        {where_clause}
        ORDER BY started_at DESC, completed_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def set_application_state(
    conn,
    app_id: str,
    state: str,
    event: str,
    actor: str = "system",
    details: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    conn.execute(
        "UPDATE applications SET state = ? WHERE id = ?",
        (state, app_id),
    )
    _insert_history(conn, app_id, state, event, actor, details)
    return get_application(conn, app_id)


def validate_transition(current: str, next_state: str) -> bool:
    allowed = {
        "pending": {"analyzing_job", "filling_form", "failed"},
        "analyzing_job": {"generating_materials", "failed"},
        "generating_materials": {"awaiting_review", "failed"},
        "awaiting_review": {"filling_form", "failed"},
        "filling_form": {"submitting", "failed"},
        "submitting": {"completed", "failed"},
        "completed": set(),
        "failed": set(),
    }
    return next_state in allowed.get(current, set())


def get_recent_history(conn, limit: int = 10) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT ah.*
        FROM application_history ah
        ORDER BY ah.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_applications_started_between(conn, start_iso: str, end_iso: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(1) AS count
        FROM applications
        WHERE started_at >= ? AND started_at < ?
        """,
        (start_iso, end_iso),
    ).fetchone()
    return int(row["count"]) if row else 0


def list_application_history(conn, app_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM application_history WHERE application_id = ? ORDER BY created_at ASC, rowid ASC",
        (app_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_application_stats(conn) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT state, COUNT(1) AS count
        FROM applications
        GROUP BY state
        """
    ).fetchall()
    stats = {row["state"]: int(row["count"]) for row in rows}
    return stats


def _insert_history(
    conn,
    app_id: str,
    state: str,
    event: str,
    actor: str,
    details: dict[str, Any] | None,
):
    conn.execute(
        """
        INSERT INTO application_history (
          id, application_id, state, event, actor, details_json, created_at
        ) VALUES (
          :id, :application_id, :state, :event, :actor, :details_json, :created_at
        )
        """,
        {
            "id": _id("hist"),
            "application_id": app_id,
            "state": state,
            "event": event,
            "actor": actor,
            "details_json": json.dumps(details) if details is not None else None,
            "created_at": _now(),
        },
    )


def log_application_event(
    conn,
    app_id: str,
    state: str,
    event: str,
    actor: str = "system",
    details: dict[str, Any] | None = None,
) -> None:
    _insert_history(conn, app_id, state, event, actor, details)


def get_material(conn, material_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM generated_content WHERE id = ?",
        (material_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def delete_material(conn, material_id: str) -> dict[str, Any] | None:
    material = get_material(conn, material_id)
    if not material:
        return None
    conn.execute("DELETE FROM generated_content WHERE id = ?", (material_id,))
    return material


def list_job_materials(
    conn,
    job_id: str,
    material_type: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    if material_type:
        rows = conn.execute(
            """
            SELECT * FROM generated_content
            WHERE job_id = ? AND type = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (job_id, material_type, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM generated_content
            WHERE job_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (job_id, limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_latest_material(
    conn,
    job_id: str,
    material_type: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM generated_content
        WHERE job_id = ? AND type = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (job_id, material_type),
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_application_artifacts(
    conn,
    application_id: str,
    artifact_type: str | None,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    if artifact_type:
        rows = conn.execute(
            """
            SELECT * FROM artifacts
            WHERE application_id = ? AND type = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (application_id, artifact_type, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM artifacts
            WHERE application_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (application_id, limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_artifact(conn, artifact_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_job_analysis(conn, job_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM job_analysis WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    if not row:
        return None
    data = _row_to_dict(row)
    try:
        data["keywords"] = json.loads(data.get("keywords_json") or "[]")
    except json.JSONDecodeError:
        data["keywords"] = []
    try:
        data["skills"] = json.loads(data.get("skills_json") or "[]")
    except json.JSONDecodeError:
        data["skills"] = []
    return data


def upsert_job_analysis(
    conn,
    job_id: str,
    keywords: list[str],
    skills: list[str],
    model_used: str,
    prompt_hash: str,
    created_at: str,
) -> dict[str, Any]:
    conn.execute(
        """
        INSERT INTO job_analysis (
          id, job_id, keywords_json, skills_json, model_used, prompt_hash, created_at
        ) VALUES (
          :id, :job_id, :keywords_json, :skills_json, :model_used, :prompt_hash, :created_at
        )
        ON CONFLICT(job_id) DO UPDATE SET
          keywords_json = excluded.keywords_json,
          skills_json = excluded.skills_json,
          model_used = excluded.model_used,
          prompt_hash = excluded.prompt_hash,
          created_at = excluded.created_at
        """,
        {
            "id": _id("analysis"),
            "job_id": job_id,
            "keywords_json": json.dumps(keywords),
            "skills_json": json.dumps(skills),
            "model_used": model_used,
            "prompt_hash": prompt_hash,
            "created_at": created_at,
        },
    )
    return get_job_analysis(conn, job_id) or {}


def get_lever_posting_cache(
    conn,
    site: str,
    posting_id: str,
    region: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM lever_postings
        WHERE site = ? AND posting_id = ? AND region = ?
        """,
        (site, posting_id, region),
    ).fetchone()
    if not row:
        return None
    data = _row_to_dict(row)
    try:
        data["payload"] = json.loads(data.get("payload_json") or "{}")
    except json.JSONDecodeError:
        data["payload"] = {}
    try:
        data["apply"] = json.loads(data.get("apply_json") or "null")
    except json.JSONDecodeError:
        data["apply"] = None
    return data


def upsert_lever_posting_cache(
    conn,
    site: str,
    posting_id: str,
    region: str,
    payload: dict[str, Any],
    apply_payload: dict[str, Any] | None,
    fetched_at: str,
) -> dict[str, Any]:
    conn.execute(
        """
        INSERT INTO lever_postings (
          id, site, posting_id, region, payload_json, apply_json, fetched_at
        ) VALUES (
          :id, :site, :posting_id, :region, :payload_json, :apply_json, :fetched_at
        )
        ON CONFLICT(site, posting_id, region) DO UPDATE SET
          payload_json = excluded.payload_json,
          apply_json = excluded.apply_json,
          fetched_at = excluded.fetched_at
        """,
        {
            "id": _id("lever"),
            "site": site,
            "posting_id": posting_id,
            "region": region,
            "payload_json": json.dumps(payload),
            "apply_json": json.dumps(apply_payload) if apply_payload is not None else None,
            "fetched_at": fetched_at,
        },
    )
    return get_lever_posting_cache(conn, site, posting_id, region) or {}


def list_selectors(
    conn, platform: str | None, limit: int, offset: int
) -> list[dict[str, Any]]:
    if platform:
        rows = conn.execute(
            """
            SELECT * FROM selector_registry
            WHERE platform = ?
            ORDER BY name ASC
            LIMIT ? OFFSET ?
            """,
            (platform, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM selector_registry
            ORDER BY name ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [_selector_row_to_dict(r) for r in rows]


def create_selector(conn, platform: str, name: str, selectors: list[str]) -> dict[str, Any]:
    selector_id = _id("sel")
    record = {
        "id": selector_id,
        "platform": platform,
        "name": name,
        "selectors_json": json.dumps(selectors),
        "success_count": 0,
        "failure_count": 0,
        "last_success_at": None,
        "last_failure_at": None,
    }
    conn.execute(
        """
        INSERT INTO selector_registry (
          id, platform, name, selectors_json, success_count, failure_count,
          last_success_at, last_failure_at
        ) VALUES (
          :id, :platform, :name, :selectors_json, :success_count, :failure_count,
          :last_success_at, :last_failure_at
        )
        """,
        record,
    )
    return _selector_row_to_dict(record)


def get_selector(conn, selector_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM selector_registry WHERE id = ?",
        (selector_id,),
    ).fetchone()
    return _selector_row_to_dict(row) if row else None


def update_selector(
    conn,
    selector_id: str,
    name: str | None,
    selectors: list[str] | None,
) -> dict[str, Any] | None:
    updates: dict[str, Any] = {}
    if name is not None:
        updates["name"] = name
    if selectors is not None:
        updates["selectors_json"] = json.dumps(selectors)

    if not updates:
        return get_selector(conn, selector_id)

    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    updates["id"] = selector_id
    conn.execute(f"UPDATE selector_registry SET {set_clause} WHERE id = :id", updates)
    return get_selector(conn, selector_id)
