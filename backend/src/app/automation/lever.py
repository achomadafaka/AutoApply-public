from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from ..settings import get_settings


@dataclass(frozen=True)
class LeverTarget:
    site: str
    posting_id: str
    region: str


@dataclass(frozen=True)
class LeverParsedUrl:
    site: str | None
    posting_id: str | None
    region: str | None


class LeverError(Exception):
    pass


class LeverNotFound(LeverError):
    pass


def _parse_region(host: str) -> str:
    if host.endswith("eu.lever.co"):
        return "eu"
    return "global"


def parse_lever_job_url(url: str) -> LeverParsedUrl | None:
    if not url or not isinstance(url, str):
        return None

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path_segments = [segment for segment in parsed.path.split("/") if segment]

    region = None
    site = None
    posting_id = None

    if host.endswith("lever.co"):
        region = _parse_region(host)
        if host.startswith("jobs.") or host.startswith("jobs.eu."):
            if len(path_segments) >= 1:
                site = path_segments[0]
            if len(path_segments) >= 2:
                posting_id = path_segments[1]
        elif host.startswith("api.") or host.startswith("api.eu."):
            if len(path_segments) >= 3 and path_segments[0] == "v0" and path_segments[1] == "postings":
                site = path_segments[2] if len(path_segments) >= 3 else None
                posting_id = path_segments[3] if len(path_segments) >= 4 else None

    if site:
        site = site.strip().strip("/")
        if not site:
            site = None
    if posting_id:
        posting_id = posting_id.strip().strip("/")
        if not posting_id:
            posting_id = None

    if site is None and posting_id is None:
        return None
    return LeverParsedUrl(site=site, posting_id=posting_id, region=region)


def fetch_lever_posting(target: LeverTarget) -> dict:
    settings = get_settings()
    base_url = "https://api.lever.co"
    if target.region == "eu":
        base_url = "https://api.eu.lever.co"

    url = f"{base_url}/v0/postings/{target.site}/{target.posting_id}"
    params = {"mode": "json"}

    try:
        with httpx.Client(timeout=settings.lever_timeout_sec) as client:
            response = client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise LeverError(f"Lever request failed: {exc}") from exc

    if response.status_code == 404:
        raise LeverNotFound("Lever job not found")

    if response.status_code >= 400:
        raise LeverError(f"Lever request failed with status {response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise LeverError("Lever response was not valid JSON") from exc


def fetch_lever_apply_fields(target: LeverTarget, api_key: str) -> dict:
    settings = get_settings()
    base_url = "https://api.lever.co"
    if target.region == "eu":
        base_url = "https://api.eu.lever.co"

    url = f"{base_url}/v0/postings/{target.site}/{target.posting_id}/apply"

    try:
        with httpx.Client(timeout=settings.lever_timeout_sec) as client:
            response = client.get(url, auth=(api_key, ""))
    except httpx.HTTPError as exc:
        raise LeverError(f"Lever request failed: {exc}") from exc

    if response.status_code == 404:
        raise LeverNotFound("Lever apply endpoint not found")

    if response.status_code >= 400:
        raise LeverError(f"Lever request failed with status {response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise LeverError("Lever response was not valid JSON") from exc


def extract_lever_apply_fields(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    fields = payload.get("fields")
    if isinstance(fields, list):
        return fields
    questions = payload.get("questions")
    if isinstance(questions, list):
        return questions
    return []


def build_selector_drafts(fields: list[dict]) -> list[dict]:
    drafts: list[dict] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        label = field.get("text") or field.get("label") or field.get("name") or "Lever field"
        name = field.get("name") or field.get("id")
        field_type = (field.get("type") or "").lower()
        selectors: list[str] = []
        if name:
            if "textarea" in field_type:
                selectors.append(f'textarea[name="{name}"]')
            elif "file" in field_type:
                selectors.append(f'input[type="file"][name="{name}"]')
            elif "select" in field_type or "dropdown" in field_type:
                selectors.append(f'select[name="{name}"]')
            else:
                selectors.append(f'input[name="{name}"]')
        if not selectors and isinstance(label, str):
            safe_label = label.strip().replace('"', '\\"')
            if safe_label:
                selectors.append(f'label:has-text("{safe_label}")')
        if selectors:
            drafts.append({"name": str(label).strip() or "Lever field", "selectors": selectors})
    return drafts
