from fastapi import APIRouter, HTTPException, Query, Response
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from hashlib import sha256
import zipfile
import xml.etree.ElementTree as ET

from ..ai import AIError, analyze_job, generate_cover_letter, tailor_resume
from ..cv_workspace import draft_protocol, pick_baseline
from ..db import db_conn
from ..settings import get_settings
from ..repo import (
    create_job,
    get_job,
    get_job_by_url,
    get_job_by_title_company,
    list_jobs,
    update_job,
    delete_job,
    get_job_analysis,
    upsert_job_analysis,
    list_job_materials,
    list_artifact_paths_for_job,
)
from ..schemas import (
    JobCreate,
    JobOut,
    JobUpdate,
    JobAnalysisOut,
    GenerateMaterialsIn,
    JobStatus,
    MaterialOut,
    TailorResumeIn,
    JobDiscoverIn,
    JobDiscoverOut,
)
from ..automation.job_discovery import (
    JobSource,
    default_keywords,
    fetch_greenhouse_board,
    fetch_lever_board,
    filter_jobs,
    normalize_greenhouse_job,
    normalize_lever_job,
    sources_from_existing_jobs,
)
from ..automation.greenhouse import parse_greenhouse_job_url
from ..automation.lever import parse_lever_job_url


router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=list[JobOut])
def jobs_list(
    status: JobStatus | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with db_conn() as conn:
        rows = list_jobs(conn, status.value if status else None, q, limit, offset)
    return rows


@router.post("/jobs", response_model=JobOut, status_code=201)
def jobs_create(payload: JobCreate, response: Response):
    data = payload.model_dump(mode="json")
    title = (data.get("title") or "").strip()
    company = (data.get("company") or "").strip()
    location = (data.get("location") or "").strip() or None
    data["title"] = title
    data["company"] = company
    data["location"] = location
    url = data.get("url")
    if url:
        url = url.strip().rstrip("/")
        data["url"] = url
    with db_conn() as conn:
        if url:
            existing = get_job_by_url(conn, url)
            if existing:
                response.status_code = 200
                response.headers["X-AutoApply-Deduped"] = "true"
                response.headers["Location"] = f"/v1/jobs/{existing['id']}"
                return existing
        else:
            existing = get_job_by_title_company(conn, title, company, location)
            if existing:
                response.status_code = 200
                response.headers["X-AutoApply-Deduped"] = "true"
                response.headers["Location"] = f"/v1/jobs/{existing['id']}"
                return existing
        job = create_job(conn, data)
    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
def jobs_get(job_id: str):
    with db_conn() as conn:
        job = get_job(conn, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/jobs/{job_id}", response_model=JobOut)
def jobs_update(job_id: str, payload: JobUpdate):
    updates = payload.model_dump(exclude_unset=True, mode="json")
    with db_conn() as conn:
        job = update_job(conn, job_id, updates)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}", response_model=JobOut)
def jobs_delete(job_id: str):
    with db_conn() as conn:
        job = get_job(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        active = conn.execute(
            """
            SELECT COUNT(1) AS count
            FROM applications
            WHERE job_id = ?
              AND state NOT IN ('completed', 'failed')
            """,
            (job_id,),
        ).fetchone()
        if active and int(active["count"]) > 0:
            raise HTTPException(status_code=409, detail="Cancel runs before deleting job")
        artifact_paths = list_artifact_paths_for_job(conn, job_id)
        deleted = delete_job(conn, job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    artifact_root = Path("artifacts").resolve()
    for path in artifact_paths:
        try:
            candidate = Path(path).resolve()
            if candidate.is_relative_to(artifact_root) and candidate.is_file():
                candidate.unlink(missing_ok=True)
        except Exception:
            continue
    return deleted


@router.post("/jobs/{job_id}/analyze", response_model=JobAnalysisOut)
def jobs_analyze(job_id: str, force: bool = Query(default=False)):
    with db_conn() as conn:
        job = get_job(conn, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    description = job.get("description") or ""
    requirements = job.get("requirements") or ""
    if not force:
        with db_conn() as conn:
            cached = get_job_analysis(conn, job_id)
        if cached:
            return JobAnalysisOut(
                source="cache",
                keywords=cached.get("keywords", []),
                skills=cached.get("skills", []),
            )
    try:
        result = analyze_job(job["title"], job["company"], description, requirements)
        if not isinstance(result.content, dict):
            raise AIError("Invalid analysis payload")
        keywords = result.content.get("keywords", [])
        skills = result.content.get("skills", [])
        with db_conn() as conn:
            upsert_job_analysis(
                conn,
                job_id,
                keywords,
                skills,
                result.model,
                result.prompt_hash,
                datetime.now(timezone.utc).isoformat(),
            )
        return JobAnalysisOut(source="ai", keywords=keywords, skills=skills)
    except AIError:
        text = f"{requirements} {description}"
        tokens = [t.strip(".,:;()").lower() for t in text.split()]
        keywords = []
        for token in tokens:
            if len(token) < 4 or token in keywords:
                continue
            keywords.append(token)
            if len(keywords) >= 10:
                break
        skills = [k for k in keywords if k.isalpha()]
        with db_conn() as conn:
            upsert_job_analysis(
                conn,
                job_id,
                keywords,
                skills[:5],
                "heuristic",
                "heuristic",
                datetime.now(timezone.utc).isoformat(),
            )
        return JobAnalysisOut(source="heuristic", keywords=keywords, skills=skills[:5])


@router.post("/jobs/discover", response_model=JobDiscoverOut)
def jobs_discover(payload: JobDiscoverIn):
    keywords = payload.keywords or default_keywords()
    remote_only = payload.remote_only
    limit = payload.limit
    sources: list[JobSource] = []

    if payload.sources:
        for source in payload.sources:
            if source.job_url:
                gh = parse_greenhouse_job_url(str(source.job_url))
                if gh and gh.board_token:
                    sources.append(JobSource(source_type="greenhouse", board=gh.board_token))
                    continue
                lever = parse_lever_job_url(str(source.job_url))
                if lever and lever.site:
                    sources.append(
                        JobSource(
                            source_type="lever",
                            site=lever.site,
                            region=lever.region or "global",
                        )
                    )
                    continue
            if source.source_type == "greenhouse" and source.board:
                sources.append(JobSource(source_type="greenhouse", board=source.board))
            if source.source_type == "lever" and source.site:
                sources.append(
                    JobSource(
                        source_type="lever",
                        site=source.site,
                        region=source.region or "global",
                    )
                )

    with db_conn() as conn:
        if not sources:
            sources = sources_from_existing_jobs(conn)

        if not sources:
            raise HTTPException(
                status_code=400,
                detail="No sources available. Add job URLs or provide board/site sources.",
            )

        created = 0
        deduped = 0
        skipped = 0
        failed = 0
        errors: list[str] = []
        used_sources: list[dict[str, Any]] = []

        for source in sources:
            try:
                if source.source_type == "greenhouse" and source.board:
                    raw_jobs = fetch_greenhouse_board(source.board)
                    normalized = [
                        normalize_greenhouse_job(source.board, job)
                        for job in raw_jobs
                    ]
                elif source.source_type == "lever" and source.site:
                    raw_jobs = fetch_lever_board(source.site, source.region or "global")
                    normalized = [
                        normalize_lever_job(source.site, job)
                        for job in raw_jobs
                    ]
                else:
                    continue
            except Exception as exc:
                failed += 1
                errors.append(f"{source.source_type}:{source.board or source.site}: {exc}")
                continue

            normalized_jobs = [job for job in normalized if job]
            filtered = filter_jobs(normalized_jobs, keywords, remote_only)
            used_sources.append(
                {
                    "source_type": source.source_type,
                    "board": source.board,
                    "site": source.site,
                    "matched": len(filtered),
                    "total": len(normalized_jobs),
                }
            )

            for job in filtered:
                if limit is not None and created >= limit:
                    break
                title = (job.get("title") or "").strip()
                company = (job.get("company") or "").strip()
                location = (job.get("location") or "").strip() or None
                url = job.get("url")
                if not title or not company:
                    skipped += 1
                    continue
                if url:
                    url = url.strip().rstrip("/")
                    existing = get_job_by_url(conn, url)
                    if existing:
                        deduped += 1
                        continue
                else:
                    existing = get_job_by_title_company(conn, title, company, location)
                    if existing:
                        deduped += 1
                        continue
                create_job(
                    conn,
                    {
                        "source": job.get("source", "discover"),
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": url,
                        "description": job.get("description"),
                        "requirements": None,
                        "remote": bool(job.get("remote")),
                        "status": "new",
                    },
                )
                created += 1

            if limit is not None and created >= limit:
                break

    return JobDiscoverOut(
        created=created,
        deduped=deduped,
        skipped=skipped,
        failed=failed,
        sources=used_sources,
        errors=errors,
    )


@router.get("/jobs/{job_id}/analysis", response_model=JobAnalysisOut)
def jobs_analysis_get(job_id: str):
    with db_conn() as conn:
        job = get_job(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        cached = get_job_analysis(conn, job_id)
    if not cached:
        raise HTTPException(status_code=404, detail="No analysis available")
    return JobAnalysisOut(
        source="cache",
        keywords=cached.get("keywords", []),
        skills=cached.get("skills", []),
    )


@router.get("/jobs/{job_id}/materials", response_model=list[MaterialOut])
def jobs_materials(
    job_id: str,
    material_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with db_conn() as conn:
        job = get_job(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        rows = list_job_materials(conn, job_id, material_type, limit, offset)
    return rows


def _resume_source(conn, existing_id: str | None, workspace_id: str | None = None) -> tuple[str, str]:
    if workspace_id:
        selected = pick_baseline(workspace_id, ".txt")
        if not selected:
            raise HTTPException(status_code=404, detail="Selected résumé is no longer available.")
        config = str(selected)
    else:
        config = get_settings().profile_base_resume_path
    if not config:
        raise HTTPException(status_code=412, detail="Set AUTOAPPLY_PROFILE_BASE_RESUME_PATH to a TXT, Markdown, or DOCX file.")
    path = Path(config).expanduser()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Configured base résumé file was not found.")
    if path.stat().st_size > 10_000_000:
        raise HTTPException(status_code=413, detail="Base résumé exceeds 10 MB.")
    try:
        if path.suffix.lower() in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8").strip()
        elif path.suffix.lower() == ".docx":
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            with zipfile.ZipFile(path) as archive:
                member = archive.getinfo("word/document.xml")
                if member.file_size > 1_000_000:
                    raise ValueError("Resume document is too large")
                root = ET.fromstring(archive.read(member))
            text = "\n".join("".join(node.text or "" for node in p.iter(ns + "t"))
                             for p in root.iter(ns + "p")).strip()
        else:
            raise HTTPException(status_code=415, detail="Use a TXT, Markdown, or DOCX base résumé.")
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise HTTPException(status_code=422, detail="The base résumé could not be read.") from exc
    if not text or len(text) > 100_000:
        raise HTTPException(status_code=422, detail="Base résumé must contain 1–100,000 text characters.")
    digest = sha256(text.encode("utf-8")).hexdigest()
    version_id = f"res_{digest}"
    if existing_id and existing_id != version_id:
        raise HTTPException(status_code=409, detail="The supplied résumé version is not the configured source. Leave it blank to use the current file.")
    conn.execute(
        "INSERT OR IGNORE INTO resume_versions (id, label, content_hash, created_at) VALUES (?, ?, ?, ?)",
        (version_id, "Configured base résumé", digest, datetime.now(timezone.utc).isoformat()),
    )
    return version_id, text


def _draft(job_id: str, kind: str, requested_resume: str | None, workspace_id: str | None = None) -> dict:
    config = get_settings()
    if config.cv_workspace and urlsplit(config.ollama_base_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=412, detail="Private workspace drafting requires Ollama on this computer.")
    with db_conn() as conn:
        job = get_job(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        version, base = _resume_source(conn, requested_resume, workspace_id)
    operation, field = ((tailor_resume, "resume") if kind == "resume_tailored"
                        else (generate_cover_letter, "cover_letter"))
    try:
        args = (base, job["title"], job["company"], job.get("description") or "", job.get("requirements") or "")
        protocol = draft_protocol()
        result = operation(*args, protocol) if protocol else operation(*args)
        content = result.content.get(field) if isinstance(result.content, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise AIError("Empty or malformed draft")
    except AIError as exc:
        raise HTTPException(status_code=503, detail="Ollama did not return a draft. Check the local model and try again.") from exc
    material_id = f"gen_{uuid4().hex[:12]}"
    with db_conn() as conn:
        conn.execute(
            """INSERT INTO generated_content
               (id, job_id, resume_version_id, type, content_text, model_used, prompt_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (material_id, job_id, version, kind, content.strip(), result.model,
             result.prompt_hash, datetime.now(timezone.utc).isoformat()),
        )
        created = conn.execute("SELECT * FROM generated_content WHERE id = ?", (material_id,)).fetchone()
    return dict(created)


@router.post("/jobs/{job_id}/generate-materials")
def jobs_generate_materials(job_id: str, payload: GenerateMaterialsIn):
    return {"created": [_draft(job_id, "cover_letter", payload.resume_version_id, payload.workspace_resume_id)]
            if payload.include_cover_letter else []}


@router.post("/jobs/{job_id}/tailor-resume", response_model=MaterialOut)
def jobs_tailor_resume(job_id: str, payload: TailorResumeIn):
    return _draft(job_id, "resume_tailored", payload.resume_version_id, payload.workspace_resume_id)
