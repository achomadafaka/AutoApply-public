from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

from ..settings import get_settings


@dataclass(frozen=True)
class GreenhouseTarget:
    board_token: str
    job_id: int


@dataclass(frozen=True)
class GreenhouseParsedUrl:
    board_token: str | None
    job_id: int | None


class GreenhouseError(Exception):
    pass


class GreenhouseNotFound(GreenhouseError):
    pass


def _first_query_value(values: list[str] | None) -> str | None:
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _parse_job_id(value: str | None) -> int | None:
    if not value:
        return None
    if value.isdigit():
        return int(value)
    return None


def parse_greenhouse_job_url(url: str) -> GreenhouseParsedUrl | None:
    if not url or not isinstance(url, str):
        return None

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    query = parse_qs(parsed.query)

    job_id = _parse_job_id(_first_query_value(query.get("gh_jid")))
    if job_id is None:
        job_id = _parse_job_id(_first_query_value(query.get("token")))
    if job_id is None:
        job_id = _parse_job_id(_first_query_value(query.get("job_id")))

    board_token = None
    if host.endswith("greenhouse.io"):
        if len(path_segments) >= 3 and path_segments[1] == "jobs":
            board_token = path_segments[0]
            if job_id is None:
                job_id = _parse_job_id(path_segments[2])
        elif path_segments:
            if path_segments[0] not in {"jobs", "embed"}:
                board_token = path_segments[0]

    if board_token is None:
        board_token = _first_query_value(query.get("for"))

    if board_token:
        board_token = board_token.strip().strip("/")
        if not board_token:
            board_token = None

    if board_token is None and job_id is None:
        return None
    return GreenhouseParsedUrl(board_token=board_token, job_id=job_id)


def fetch_greenhouse_job(
    target: GreenhouseTarget,
    include_questions: bool,
    include_pay_transparency: bool,
) -> dict:
    settings = get_settings()
    params: dict[str, str] = {}
    if include_questions:
        params["questions"] = "true"
    if include_pay_transparency:
        params["pay_transparency"] = "true"

    url = (
        "https://boards-api.greenhouse.io/v1/boards/"
        f"{target.board_token}/jobs/{target.job_id}"
    )

    try:
        with httpx.Client(timeout=settings.greenhouse_timeout_sec) as client:
            response = client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise GreenhouseError(f"Greenhouse request failed: {exc}") from exc

    if response.status_code == 404:
        raise GreenhouseNotFound("Greenhouse job not found")

    if response.status_code >= 400:
        raise GreenhouseError(
            f"Greenhouse request failed with status {response.status_code}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise GreenhouseError("Greenhouse response was not valid JSON") from exc
