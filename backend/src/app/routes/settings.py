from fastapi import APIRouter

from ..schemas import SettingsOut, SettingsUpdate
from ..settings import get_settings
from ..settings_store import load_settings, save_settings

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsOut)
def settings_get():
    config = get_settings()
    stored = load_settings(config.settings_path)
    return SettingsOut(daily_limit=stored.get("daily_limit", config.daily_limit))


@router.patch("/settings", response_model=SettingsOut)
def settings_update(payload: SettingsUpdate):
    config = get_settings()
    current = settings_get()
    daily_limit = payload.daily_limit if payload.daily_limit is not None else current.daily_limit
    save_settings(config.settings_path, {"daily_limit": daily_limit})
    return SettingsOut(daily_limit=daily_limit)
