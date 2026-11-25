from uuid import uuid4
from fastapi import APIRouter, HTTPException

from ..automation.greenhouse import (
    GreenhouseError,
    GreenhouseNotFound,
    GreenhouseTarget,
    fetch_greenhouse_job,
    parse_greenhouse_job_url,
)
from datetime import datetime, timezone

from ..automation.lever import (
    LeverError,
    LeverNotFound,
    LeverTarget,
    build_selector_drafts,
    extract_lever_apply_fields,
    fetch_lever_apply_fields,
    fetch_lever_posting,
    parse_lever_job_url,
)
from ..db import db_conn
from ..repo import get_lever_posting_cache, upsert_lever_posting_cache
from ..settings import get_settings
from ..schemas import (
    AutomationSessionIn,
    AutomationSessionOut,
    GreenhouseInspectIn,
    GreenhouseInspectOut,
    LeverInspectIn,
    LeverInspectOut,
)


router = APIRouter(tags=["automation"])


@router.post("/automation/session", response_model=AutomationSessionOut)
def automation_session(payload: AutomationSessionIn):
    return AutomationSessionOut(
        session_id=f"session_{uuid4().hex[:12]}",
        headless=payload.headless,
    )


@router.post("/automation/greenhouse/inspect", response_model=GreenhouseInspectOut)
def greenhouse_inspect(payload: GreenhouseInspectIn):
    board_token = payload.board_token.strip().strip("/") if payload.board_token else None
    job_id = payload.job_id

    if payload.job_url:
        parsed = parse_greenhouse_job_url(str(payload.job_url))
        if parsed:
            if board_token is None:
                board_token = parsed.board_token
            if job_id is None:
                job_id = parsed.job_id

    if not board_token or job_id is None:
        raise HTTPException(
            status_code=400,
            detail="Provide a Greenhouse job_url or include board_token and job_id.",
        )

    target = GreenhouseTarget(board_token=board_token, job_id=job_id)
    try:
        data = fetch_greenhouse_job(
            target,
            include_questions=payload.include_questions,
            include_pay_transparency=payload.include_pay_transparency,
        )
    except GreenhouseNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GreenhouseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    location = data.get("location")
    location_name = location.get("name") if isinstance(location, dict) else location

    return GreenhouseInspectOut(
        board_token=board_token,
        job_id=job_id,
        title=data.get("title"),
        location=location_name,
        absolute_url=data.get("absolute_url"),
        updated_at=data.get("updated_at"),
        questions=data.get("questions") or [],
        location_questions=data.get("location_questions") or [],
        compliance=data.get("compliance") or [],
        data_compliance=data.get("data_compliance") or [],
        demographic_questions=data.get("demographic_questions"),
        pay_input_ranges=data.get("pay_input_ranges") or [],
        raw=data,
    )


@router.post("/automation/lever/inspect", response_model=LeverInspectOut)
def lever_inspect(payload: LeverInspectIn):
    site = payload.site.strip().strip("/") if payload.site else None
    posting_id = payload.posting_id.strip().strip("/") if payload.posting_id else None
    region = payload.region.strip().lower() if payload.region else None

    if payload.job_url:
        parsed = parse_lever_job_url(str(payload.job_url))
        if parsed:
            if site is None:
                site = parsed.site
            if posting_id is None:
                posting_id = parsed.posting_id
            if region is None:
                region = parsed.region

    if not site or not posting_id:
        raise HTTPException(
            status_code=400,
            detail="Provide a Lever job_url or include site and posting_id.",
        )

    if not region:
        region = "global"

    settings = get_settings()
    want_apply = payload.include_apply_fields or payload.include_selector_drafts
    use_cache = not payload.force
    cached_at = None
    source = "lever"
    data = None
    apply_payload = None

    if use_cache:
        with db_conn() as conn:
            cached = get_lever_posting_cache(conn, site, posting_id, region)
        if cached:
            cached_at = cached.get("fetched_at")
            ttl = settings.lever_cache_ttl_sec
            if ttl > 0 and cached_at:
                try:
                    fetched_dt = datetime.fromisoformat(cached_at)
                    if fetched_dt.tzinfo is None:
                        fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - fetched_dt).total_seconds()
                    if age <= ttl:
                        data = cached.get("payload")
                        apply_payload = cached.get("apply")
                        if not want_apply or apply_payload:
                            source = "cache"
                        else:
                            data = None
                            apply_payload = None
                            cached_at = None
                except ValueError:
                    pass

    if data is None:
        target = LeverTarget(site=site, posting_id=posting_id, region=region)
        try:
            data = fetch_lever_posting(target)
        except LeverNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except LeverError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        if want_apply:
            if not settings.lever_api_key:
                raise HTTPException(
                    status_code=412,
                    detail="Lever API key not configured.",
                )
            try:
                apply_payload = fetch_lever_apply_fields(target, settings.lever_api_key)
            except LeverNotFound as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except LeverError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        cached_at = datetime.now(timezone.utc).isoformat()
        with db_conn() as conn:
            upsert_lever_posting_cache(conn, site, posting_id, region, data, apply_payload, cached_at)

    categories = data.get("categories") or {}
    location = categories.get("location") if isinstance(categories, dict) else None
    team = categories.get("team") if isinstance(categories, dict) else None
    commitment = categories.get("commitment") if isinstance(categories, dict) else None
    workplace_type = categories.get("workplaceType") if isinstance(categories, dict) else None
    apply_fields = extract_lever_apply_fields(apply_payload) if apply_payload else []
    selector_drafts = build_selector_drafts(apply_fields) if payload.include_selector_drafts else []

    return LeverInspectOut(
        source=source,
        site=site,
        posting_id=posting_id,
        region=region,
        cached_at=cached_at,
        title=data.get("text"),
        location=location,
        team=team,
        commitment=commitment,
        workplace_type=workplace_type,
        hosted_url=data.get("hostedUrl"),
        apply_url=data.get("applyUrl"),
        description=data.get("description"),
        lists=data.get("lists") or [],
        apply_fields=apply_fields if payload.include_apply_fields else [],
        selector_drafts=selector_drafts,
        raw=data,
    )
