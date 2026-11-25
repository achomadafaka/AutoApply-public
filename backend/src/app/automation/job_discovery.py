from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .greenhouse import parse_greenhouse_job_url
from .lever import parse_lever_job_url
from ..settings import get_settings


@dataclass(frozen=True)
class JobSource:
    source_type: str
    board: str | None = None
    site: str | None = None
    region: str | None = None


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _is_remote_text(value: str | None) -> bool:
    text = _normalize_text(value)
    if not text:
        return False
    return any(token in text for token in ("remote", "anywhere", "distributed"))


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = _normalize_text(text)
    return any(keyword in haystack for keyword in keywords)


def default_keywords() -> list[str]:
    return [
        "ai",
        "artificial intelligence",
        "machine learning",
        "ml",
        "deep learning",
        "data",
        "data engineer",
        "data scientist",
        "analytics",
        "software",
        "software engineer",
        "swe",
        "backend",
        "frontend",
        "front end",
        "full stack",
        "full-stack",
        "web",
        "platform",
        "infrastructure",
        "devops",
        "cloud",
    ]


def sources_from_existing_jobs(conn) -> list[JobSource]:
    rows = conn.execute(
        "SELECT url FROM job_listings WHERE url IS NOT NULL AND url != ''"
    ).fetchall()
    sources: dict[tuple[str, str], JobSource] = {}
    for row in rows:
        url = row["url"]
        parsed_gh = parse_greenhouse_job_url(url)
        if parsed_gh and parsed_gh.board_token:
            key = ("greenhouse", parsed_gh.board_token)
            sources[key] = JobSource(source_type="greenhouse", board=parsed_gh.board_token)
            continue
        parsed_lever = parse_lever_job_url(url)
        if parsed_lever and parsed_lever.site:
            key = ("lever", parsed_lever.site)
            sources[key] = JobSource(
                source_type="lever",
                site=parsed_lever.site,
                region=parsed_lever.region or "global",
            )
    return list(sources.values())


def fetch_greenhouse_board(board_token: str) -> list[dict[str, Any]]:
    settings = get_settings()
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    params = {"content": "true"}
    with httpx.Client(timeout=settings.greenhouse_timeout_sec) as client:
        response = client.get(url, params=params)
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    if not isinstance(jobs, list):
        return []
    return jobs


def fetch_lever_board(site: str, region: str) -> list[dict[str, Any]]:
    settings = get_settings()
    base_url = "https://api.lever.co" if region != "eu" else "https://api.eu.lever.co"
    url = f"{base_url}/v0/postings/{site}"
    params = {"mode": "json"}
    with httpx.Client(timeout=settings.lever_timeout_sec) as client:
        response = client.get(url, params=params)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    return payload


def normalize_greenhouse_job(board_token: str, job: dict[str, Any]) -> dict[str, Any] | None:
    title = (job.get("title") or "").strip()
    if not title:
        return None
    location = None
    location_obj = job.get("location")
    if isinstance(location_obj, dict):
        location = location_obj.get("name")
    elif isinstance(location_obj, str):
        location = location_obj
    url = job.get("absolute_url")
    description = job.get("content")
    return {
        "source": "greenhouse",
        "title": title,
        "company": board_token,
        "location": location,
        "url": url,
        "description": description,
        "remote": _is_remote_text(location) or _is_remote_text(description),
        "raw": job,
    }


def normalize_lever_job(site: str, job: dict[str, Any]) -> dict[str, Any] | None:
    title = (job.get("text") or "").strip()
    if not title:
        return None
    categories = job.get("categories") or {}
    location = categories.get("location") or job.get("location")
    url = job.get("hostedUrl") or job.get("applyUrl")
    description = job.get("descriptionPlain") or job.get("description")
    workplace = job.get("workplaceType")
    return {
        "source": "lever",
        "title": title,
        "company": site,
        "location": location,
        "url": url,
        "description": description,
        "remote": _is_remote_text(location) or _is_remote_text(workplace) or _is_remote_text(description),
        "raw": job,
    }


def filter_jobs(
    jobs: list[dict[str, Any]],
    keywords: list[str],
    remote_only: bool,
) -> list[dict[str, Any]]:
    filtered = []
    normalized_keywords = [_normalize_text(k) for k in keywords if _normalize_text(k)]
    for job in jobs:
        text = f"{job.get('title','')} {job.get('description','')} {job.get('location','')}"
        if remote_only and not job.get("remote"):
            continue
        if not _matches_keywords(text, normalized_keywords):
            continue
        filtered.append(job)
    return filtered
