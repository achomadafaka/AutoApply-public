"""Optional local résumé catalog. No arbitrary path or directory access from the UI."""

import re
from pathlib import Path

from .settings import get_settings

ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")


def _file(relative: str) -> Path | None:
    configured = get_settings().cv_workspace
    if not configured:
        return None
    root = Path(configured).expanduser().resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    return path


def pick_baseline(resume_id: str, suffix: str) -> Path | None:
    if not ID.fullmatch(resume_id) or suffix not in {".txt", ".pdf"}:
        return None
    return _file(f"baselines/{resume_id}{suffix}")


def list_baselines() -> list[dict[str, str]]:
    configured = get_settings().cv_workspace
    if not configured:
        return []
    base = Path(configured).expanduser() / "baselines"
    return [
        {"id": file.stem, "label": file.stem.replace("-", " ").title()}
        for file in sorted(base.glob("*.pdf"))
        if pick_baseline(file.stem, ".pdf") and pick_baseline(file.stem, ".txt")
    ]


def draft_protocol() -> str:
    path = _file("protocols/DRAFTING.md")
    return path.read_text(encoding="utf-8") if path and path.stat().st_size <= 16_000 else ""
