from enum import Enum
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from typing import Any, Optional


class JobSource(str, Enum):
    manual = "manual"
    import_ = "import"
    greenhouse = "greenhouse"
    lever = "lever"
    discover = "discover"


class JobStatus(str, Enum):
    new = "new"
    applied = "applied"
    archived = "archived"


class ApplicationMode(str, Enum):
    fill_review = "fill_review"
    assisted = "assisted"
    auto = "auto"


class ApplicationState(str, Enum):
    pending = "pending"
    analyzing_job = "analyzing_job"
    generating_materials = "generating_materials"
    awaiting_review = "awaiting_review"
    filling_form = "filling_form"
    submitting = "submitting"
    completed = "completed"
    failed = "failed"


class Platform(str, Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    other = "other"


class HealthOut(BaseModel):
    status: str = "ok"


class JobCreate(BaseModel):
    source: JobSource = JobSource.manual
    title: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=120)
    url: Optional[HttpUrl] = None
    location: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=10000)
    requirements: Optional[str] = Field(default=None, max_length=10000)

    @field_validator("title", "company", mode="before")
    @classmethod
    def _strip_required(cls, value):
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("Field is required")
        return value

    @field_validator("location", "description", "requirements", "url", mode="before")
    @classmethod
    def _strip_optional(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value or None


class JobUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    company: Optional[str] = Field(default=None, max_length=120)
    url: Optional[HttpUrl] = None
    location: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=10000)
    requirements: Optional[str] = Field(default=None, max_length=10000)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    remote: Optional[bool] = None
    status: Optional[JobStatus] = None

    @field_validator(
        "title",
        "company",
        "location",
        "description",
        "requirements",
        "url",
        mode="before",
    )
    @classmethod
    def _strip_optional_update(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value or None


class JobSourceIn(BaseModel):
    source_type: str = Field(pattern="^(greenhouse|lever)$")
    board: Optional[str] = None
    site: Optional[str] = None
    region: Optional[str] = None
    job_url: Optional[HttpUrl] = None

    @model_validator(mode="after")
    def _validate_source(self):
        if self.job_url:
            return self
        if self.source_type == "greenhouse" and self.board:
            return self
        if self.source_type == "lever" and self.site:
            return self
        raise ValueError("Provide job_url or a board/site for the selected source_type")


class JobDiscoverIn(BaseModel):
    sources: Optional[list[JobSourceIn]] = None
    remote_only: bool = True
    keywords: list[str] = Field(default_factory=list)
    limit: Optional[int] = Field(default=None, ge=1, le=500)


class JobDiscoverOut(BaseModel):
    created: int
    deduped: int
    skipped: int
    failed: int
    sources: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ProfileAnswersOut(BaseModel):
    platform: Optional[str] = None
    answers: dict[str, Any] = Field(default_factory=dict)


class ProfileAnswersUpdate(BaseModel):
    platform: Optional[str] = None
    answers: dict[str, Optional[str]] = Field(default_factory=dict)


class JobOut(BaseModel):
    id: str
    source: JobSource
    title: str
    company: str
    location: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    remote: bool = False
    status: JobStatus
    created_at: str
    updated_at: str


class JobAnalysisOut(BaseModel):
    source: str = "ai"
    keywords: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class GenerateMaterialsIn(BaseModel):
    workspace_resume_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    resume_version_id: Optional[str] = None
    include_cover_letter: bool = True


class TailorResumeIn(BaseModel):
    workspace_resume_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    resume_version_id: Optional[str] = None


class MaterialOut(BaseModel):
    id: str
    job_id: str
    resume_version_id: str
    type: str
    content_text: str
    model_used: str
    prompt_hash: str
    rating: Optional[int] = None
    created_at: str


class ArtifactOut(BaseModel):
    id: str
    application_id: str
    type: str
    path: str
    created_at: str


class ApplicationCreate(BaseModel):
    job_id: str = Field(min_length=1)
    platform: Platform
    mode: ApplicationMode = ApplicationMode.fill_review


class FillReviewStartIn(BaseModel):
    workspace_resume_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    contact_only: bool = False
    include_phone: bool = False
    confirmed_answers: dict[str, str] = Field(default_factory=dict, max_length=10)
    phone_country: str | None = Field(default=None, max_length=80)


class ApplicationOut(BaseModel):
    id: str
    job_id: str
    platform: Platform
    mode: ApplicationMode
    state: ApplicationState
    last_error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ApplicationHistoryOut(BaseModel):
    id: str
    application_id: str
    state: ApplicationState
    event: str
    actor: str
    details_json: Optional[str] = None
    created_at: str


class AutomationSessionIn(BaseModel):
    headless: bool = False


class AutomationSessionOut(BaseModel):
    session_id: str
    headless: bool


class GreenhouseInspectIn(BaseModel):
    job_url: Optional[HttpUrl] = None
    board_token: Optional[str] = Field(default=None, min_length=1, max_length=120)
    job_id: Optional[int] = Field(default=None, ge=1)
    include_questions: bool = True
    include_pay_transparency: bool = False


class GreenhouseInspectOut(BaseModel):
    source: str = "greenhouse"
    board_token: str
    job_id: int
    title: Optional[str] = None
    location: Optional[str] = None
    absolute_url: Optional[str] = None
    updated_at: Optional[str] = None
    questions: list[dict[str, Any]] = Field(default_factory=list)
    location_questions: list[dict[str, Any]] = Field(default_factory=list)
    compliance: list[dict[str, Any]] = Field(default_factory=list)
    data_compliance: list[dict[str, Any]] = Field(default_factory=list)
    demographic_questions: dict[str, Any] | None = None
    pay_input_ranges: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class LeverInspectIn(BaseModel):
    job_url: Optional[HttpUrl] = None
    site: Optional[str] = Field(default=None, min_length=1, max_length=120)
    posting_id: Optional[str] = Field(default=None, min_length=1, max_length=200)
    region: Optional[str] = Field(default=None, max_length=20)
    force: bool = False
    include_apply_fields: bool = False
    include_selector_drafts: bool = False


class SelectorDraftOut(BaseModel):
    name: str
    selectors: list[str] = Field(default_factory=list)


class LeverInspectOut(BaseModel):
    source: str = "lever"
    site: str
    posting_id: str
    region: str
    cached_at: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    team: Optional[str] = None
    commitment: Optional[str] = None
    workplace_type: Optional[str] = None
    hosted_url: Optional[str] = None
    apply_url: Optional[str] = None
    description: Optional[str] = None
    lists: list[dict[str, Any]] = Field(default_factory=list)
    apply_fields: list[dict[str, Any]] = Field(default_factory=list)
    selector_drafts: list[SelectorDraftOut] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class AIHealthOut(BaseModel):
    status: str
    base_url: str
    analyze_model: str
    generate_model: str
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class SettingsOut(BaseModel):
    daily_limit: int


class SettingsUpdate(BaseModel):
    daily_limit: Optional[int] = Field(default=None, ge=1, le=200)


class ApplicationStatsOut(BaseModel):
    pending_review: int
    in_progress: int
    completed: int
    failed: int
    total: int


class SelectorCreate(BaseModel):
    platform: Platform
    name: str = Field(min_length=1, max_length=100)
    selectors: list[str] = Field(min_length=1)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value):
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("Name is required")
        return value

    @field_validator("selectors", mode="before")
    @classmethod
    def _normalize_selectors(cls, value):
        if not isinstance(value, list):
            raise ValueError("Selectors must be a list")
        cleaned = []
        for item in value:
            if not isinstance(item, str):
                continue
            selector = item.strip()
            if selector:
                cleaned.append(selector)
        if not cleaned:
            raise ValueError("At least one selector is required")
        return cleaned


class SelectorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    selectors: Optional[list[str]] = None

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name_update(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value or None

    @field_validator("selectors", mode="before")
    @classmethod
    def _normalize_selectors_update(cls, value):
        if value is None:
            return value
        if not isinstance(value, list):
            raise ValueError("Selectors must be a list")
        cleaned = []
        for item in value:
            if not isinstance(item, str):
                continue
            selector = item.strip()
            if selector:
                cleaned.append(selector)
        if not cleaned:
            raise ValueError("At least one selector is required")
        return cleaned


class SelectorOut(BaseModel):
    id: str
    platform: Platform
    name: str
    selectors: list[str]
    success_count: int
    failure_count: int
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorOut(BaseModel):
    error: ErrorDetail
