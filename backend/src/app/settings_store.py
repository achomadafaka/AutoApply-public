import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def load_settings(path: str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    limit = data.get("daily_limit")
    return {"daily_limit": limit} if type(limit) is int and 1 <= limit <= 200 else {}


def save_settings(path: str, data: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as f:
        temp = Path(f.name)
        try:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
