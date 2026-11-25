from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_list(value: str | None, default: list[str]) -> list[str]:
    if value is None or value.strip() == "":
        return default
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@dataclass(frozen=True)
class Settings:
    api_prefix: str
    database_path: str
    settings_path: str
    cors_origins: list[str]
    daily_limit: int
    automation_enabled: bool
    automation_driver: str
    automation_interactive_timeout_sec: float
    greenhouse_timeout_sec: float
    lever_timeout_sec: float
    lever_cache_ttl_sec: int
    lever_api_key: str | None
    cv_workspace: str | None
    profile_first_name: str | None
    profile_last_name: str | None
    profile_email: str | None
    profile_phone: str | None
    profile_linkedin: str | None
    profile_github: str | None
    profile_website: str | None
    profile_location: str | None
    profile_resume_path: str | None
    profile_cover_letter_path: str | None
    profile_base_resume_path: str | None
    profile_answers_path: str | None
    ollama_base_url: str
    ollama_analyze_model: str
    ollama_generate_model: str
    ollama_timeout_sec: float


_SETTINGS: Settings | None = None


def get_settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is not None:
        return _SETTINGS

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")

    api_prefix = os.getenv("AUTOAPPLY_API_PREFIX", "/v1")
    database_path = os.getenv("AUTOAPPLY_DB_PATH", "data/autoapply.db")
    settings_path = os.getenv("AUTOAPPLY_SETTINGS_PATH", "data/settings.json")
    cors_origins = _parse_list(
        os.getenv("AUTOAPPLY_CORS_ORIGINS"),
        ["http://localhost:5173", "http://127.0.0.1:5173"],
    )
    daily_limit = min(200, max(1, _parse_int(os.getenv("AUTOAPPLY_DAILY_LIMIT"), 25)))
    automation_enabled = _parse_bool(os.getenv("AUTOAPPLY_AUTOMATION_ENABLED"), False)
    automation_driver = os.getenv("AUTOAPPLY_AUTOMATION_DRIVER", "stub").strip().lower()
    automation_interactive_timeout_sec = _parse_float(
        os.getenv("AUTOAPPLY_AUTOMATION_INTERACTIVE_TIMEOUT_SEC"),
        1800.0,
    )
    greenhouse_timeout_sec = _parse_float(os.getenv("AUTOAPPLY_GREENHOUSE_TIMEOUT_SEC"), 20.0)
    lever_timeout_sec = _parse_float(os.getenv("AUTOAPPLY_LEVER_TIMEOUT_SEC"), 20.0)
    lever_cache_ttl_sec = _parse_int(os.getenv("AUTOAPPLY_LEVER_CACHE_TTL_SEC"), 3600)
    lever_api_key = os.getenv("AUTOAPPLY_LEVER_API_KEY")
    profile_first_name = _parse_str(os.getenv("AUTOAPPLY_PROFILE_FIRST_NAME"))
    profile_last_name = _parse_str(os.getenv("AUTOAPPLY_PROFILE_LAST_NAME"))
    profile_email = _parse_str(os.getenv("AUTOAPPLY_PROFILE_EMAIL"))
    profile_phone = _parse_str(os.getenv("AUTOAPPLY_PROFILE_PHONE"))
    profile_linkedin = _parse_str(os.getenv("AUTOAPPLY_PROFILE_LINKEDIN"))
    profile_github = _parse_str(os.getenv("AUTOAPPLY_PROFILE_GITHUB"))
    profile_website = _parse_str(os.getenv("AUTOAPPLY_PROFILE_WEBSITE"))
    profile_location = _parse_str(os.getenv("AUTOAPPLY_PROFILE_LOCATION"))
    profile_resume_path = _parse_str(os.getenv("AUTOAPPLY_PROFILE_RESUME_PATH"))
    profile_cover_letter_path = _parse_str(os.getenv("AUTOAPPLY_PROFILE_COVER_LETTER_PATH"))
    profile_base_resume_path = _parse_str(os.getenv("AUTOAPPLY_PROFILE_BASE_RESUME_PATH"))
    profile_answers_path = _parse_str(os.getenv("AUTOAPPLY_PROFILE_ANSWERS_PATH"))
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_analyze_model = os.getenv("OLLAMA_ANALYZE_MODEL", "llama3.1:8b")
    ollama_generate_model = os.getenv("OLLAMA_GENERATE_MODEL", "qwen2.5:7b")
    ollama_timeout_sec = _parse_float(os.getenv("OLLAMA_TIMEOUT_SEC"), 60.0)

    _SETTINGS = Settings(
        api_prefix=api_prefix,
        database_path=database_path,
        settings_path=settings_path,
        cors_origins=cors_origins,
        daily_limit=daily_limit,
        automation_enabled=automation_enabled,
        automation_driver=automation_driver,
        automation_interactive_timeout_sec=automation_interactive_timeout_sec,
        greenhouse_timeout_sec=greenhouse_timeout_sec,
        lever_timeout_sec=lever_timeout_sec,
        lever_cache_ttl_sec=lever_cache_ttl_sec,
        lever_api_key=lever_api_key,
        cv_workspace=_parse_str(os.getenv("AUTOAPPLY_CV_WORKSPACE")),
        profile_first_name=profile_first_name,
        profile_last_name=profile_last_name,
        profile_email=profile_email,
        profile_phone=profile_phone,
        profile_linkedin=profile_linkedin,
        profile_github=profile_github,
        profile_website=profile_website,
        profile_location=profile_location,
        profile_resume_path=profile_resume_path,
        profile_cover_letter_path=profile_cover_letter_path,
        profile_base_resume_path=profile_base_resume_path,
        profile_answers_path=profile_answers_path,
        ollama_base_url=ollama_base_url,
        ollama_analyze_model=ollama_analyze_model,
        ollama_generate_model=ollama_generate_model,
        ollama_timeout_sec=ollama_timeout_sec,
    )
    return _SETTINGS
