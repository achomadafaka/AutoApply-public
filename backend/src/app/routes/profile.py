from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..cv_workspace import draft_protocol, list_baselines, pick_baseline

from ..schemas import ProfileAnswersOut, ProfileAnswersUpdate
from ..settings import get_settings


router = APIRouter(tags=["profile"])


def _load_answers(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_answers(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


@router.get("/profile/answers", response_model=ProfileAnswersOut)
def profile_answers_get(platform: str | None = Query(default=None)):
    settings = get_settings()
    if not settings.profile_answers_path:
        raise HTTPException(status_code=412, detail="Profile answers path not configured")
    path = Path(settings.profile_answers_path)
    data = _load_answers(path)
    if platform and isinstance(data.get(platform), dict):
        return ProfileAnswersOut(platform=platform, answers=data.get(platform, {}))
    return ProfileAnswersOut(platform=platform, answers=data)


@router.patch("/profile/answers", response_model=ProfileAnswersOut)
def profile_answers_update(payload: ProfileAnswersUpdate):
    settings = get_settings()
    if not settings.profile_answers_path:
        raise HTTPException(status_code=412, detail="Profile answers path not configured")
    path = Path(settings.profile_answers_path)
    data = _load_answers(path)
    platform = payload.platform or "greenhouse"
    platform_data = data.get(platform)
    if not isinstance(platform_data, dict):
        platform_data = {}
    for key, value in payload.answers.items():
        if value is None:
            platform_data.pop(key, None)
        else:
            platform_data[key] = value
    data[platform] = platform_data
    _save_answers(path, data)
    return ProfileAnswersOut(platform=platform, answers=platform_data)


@router.get("/profile/cv-workspace")
def cv_workspace_info():
    return {"baselines": list_baselines(), "drafting_protocol_loaded": bool(draft_protocol())}


@router.get("/profile/cv-workspace/{resume_id}/preview")
def cv_workspace_preview(resume_id: str):
    pdf = pick_baseline(resume_id, ".pdf")
    if not pdf:
        raise HTTPException(status_code=404, detail="Résumé not found.")
    return FileResponse(pdf, media_type="application/pdf", filename=pdf.name,
                        content_disposition_type="inline", headers={"Cache-Control": "no-store"})
