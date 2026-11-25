from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..db import db_conn
from ..repo import get_artifact, list_application_artifacts
from ..schemas import ArtifactOut


router = APIRouter(tags=["artifacts"])


@router.get("/applications/{app_id}/artifacts", response_model=list[ArtifactOut])
def artifacts_list(
    app_id: str,
    artifact_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with db_conn() as conn:
        rows = list_application_artifacts(conn, app_id, artifact_type, limit, offset)
    return rows


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
def artifacts_get(artifact_id: str):
    with db_conn() as conn:
        artifact = get_artifact(conn, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.get("/artifacts/{artifact_id}/file")
def artifacts_file(artifact_id: str):
    with db_conn() as conn:
        artifact = get_artifact(conn, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    path = Path(artifact["path"]).expanduser().resolve()
    root = Path("artifacts").resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=403, detail="Artifact path not allowed")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file missing")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream",
                        headers={"X-Content-Type-Options": "nosniff"})
