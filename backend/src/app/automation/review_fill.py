"""Greenhouse fill-and-review. Only explicit values; no submission."""
import json
import re
from urllib.parse import urlsplit

HOSTS = {"job-boards.greenhouse.io", "job-boards.eu.greenhouse.io", "boards.greenhouse.io"}
FORM = "form#application_form, form#application-form, form:has(input#first_name):has(input#email)"

PROFILE_FIELDS = {
    "first_name": "first_name", "first name": "first_name",
    "last_name": "last_name", "last name": "last_name",
    "email": "email", "email address": "email",
    "phone": "phone", "phone number": "phone",
    "linkedin profile": "linkedin", "linkedin profile url": "linkedin", "linkedin": "linkedin",
    "github": "github", "github profile": "github",
    "website": "website", "portfolio": "website",
}


def allowed_target(url: str | None) -> bool:
    if not url:
        return False
    try:
        parts = urlsplit(url)
        return (parts.scheme == "https" and parts.netloc.lower() in HOSTS
                and not parts.username and not parts.password)
    except ValueError:
        return False


def review_evidence(page, target: str) -> str | None:
    """Return only a fixed evidence code; never store form text, values or URL parameters."""
    current = page.url
    if not allowed_target(target) or not allowed_target(current):
        return None
    source, dest = urlsplit(target), urlsplit(current)
    job_path = source.path.rstrip("/")
    if (source.netloc != dest.netloc
            or not re.fullmatch(r"/[^/]+/jobs/[0-9]+", job_path)):
        return None
    dest_path = dest.path.rstrip("/")
    if dest_path == job_path + "/confirmation":
        if any(h.is_visible() for h in page.get_by_role(
            "heading", name="Thank you for applying!", exact=True
        ).all()) and not page.locator(FORM).count():
            return "confirmed"
    if dest_path == job_path:
        code = page.locator("form input#security-input-0")
        if code.count() == 1 and code.is_visible():
            return "verification"
    return None


def exact_label(value: str) -> str:
    return " ".join(value.strip().rstrip("*").casefold().split())


# Keep the write surface deliberately small. Employer questions, custom widgets and uploads
# are always entered by the applicant. A matching ID cannot override a conflicting label.
FIELD_TYPES = {
    "first_name": {"text"}, "last_name": {"text"}, "email": {"email", "text"},
    "phone": {"tel", "text"}, "linkedin": {"url", "text"},
    "github": {"url", "text"}, "website": {"url", "text"},
}
SETTLE_MS = 700
CONTROL_INFO = """el => {
    const wrapper = el.closest('.field, .application-field, .form-field, .select__container');
    const label = (el.type === 'radio' && el.closest('fieldset')?.querySelector('legend')?.textContent)
      || el.labels?.[0]?.textContent || el.getAttribute('aria-label')
      || wrapper?.querySelector('label')?.textContent || '';
    return { label: label.trim(), name: el.name, id: el.id, type: el.type,
      complex: !!el.closest('[role="combobox"], .select__container') || el.hasAttribute('role')
        || !!el.list,
      disabled: el.matches(':disabled') || el.readOnly,
      required: el.required || /\\*\\s*$/.test(label)
        || el.getAttribute('aria-required') === 'true'
        || !!wrapper?.classList.contains('required') };
}"""


def _controls(form):
    fields = form.locator("input:not([type=hidden]), textarea, select")
    for field in fields.all():
        try:
            info = field.evaluate(CONTROL_INFO)
            typ = info["type"]
            if info["disabled"] or typ in {"submit", "button", "reset", "image"}:
                continue
            if typ != "file" and not field.is_visible():
                continue
            yield field, info
        except Exception:
            continue


def _profile_key(info):
    label = exact_label(info["label"])
    key = PROFILE_FIELDS.get(label)
    id_key = PROFILE_FIELDS.get(exact_label(info["id"] or info["name"]))
    if (key and (not id_key or id_key == key) and info["type"] in FIELD_TYPES[key]
            and not info["complex"]):
        return key
    return None


def fill_form(form, profile):
    """Enter only unique, explicitly labelled contact text fields. Never click anything."""
    fields = [(field, info, _profile_key(info)) for field, info in _controls(form)]
    counts = {key: sum(match == key for _, _, match in fields) for key in FIELD_TYPES}
    for field, info, key in fields:
        value = profile.get(key)
        # Refuse ambiguous duplicates and do not write through position-based locators.
        if not value or counts[key] != 1 or not info["id"]:
            continue
        try:
            stable = form.locator(f"[id={json.dumps(info['id'])}]")
            current = stable.evaluate(CONTROL_INFO, timeout=1000)
            if not current["disabled"] and _profile_key(current) == key:
                stable.fill(value, timeout=1500)
        except Exception:
            continue
    form.evaluate("(form, ms) => new Promise(resolve => setTimeout(resolve, ms))", SETTLE_MS)
    return inspect_form(form, profile)


def inspect_form(form, profile):
    """Read current fields, never infer that an attachment was uploaded or a form is ready."""
    blockers = []
    seen = set()
    filled = 0
    for field, info in _controls(form):
        typ = info["type"]
        name = info["id"] or info["name"]
        label = info["label"] or name or "Unlabelled field"
        key = _profile_key(info)
        expected = profile.get(key)
        if expected:
            try:
                valid = field.evaluate(r"""(el, expected) => {
                    if (!el.validity.valid || !el.value.trim()) return false;
                    const phone = val => val.replace(/[^0-9]/g, '');
                    return (el.type === 'tel' ? phone(el.value) === phone(expected)
                       : el.value.trim() === expected.trim())
                       && (el.id !== 'email' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(el.value.trim()));
                }""", expected, timeout=1000)
            except Exception:
                valid = False
            if valid:
                filled += 1
                continue
        if typ == "file":
            label += " (attach or verify manually on the employer’s form)"
        if (info["required"] or expected or typ == "file") and (label, typ) not in seen:
            seen.add((label, typ))
            blockers.append({"label": label, "name": name, "type": typ,
                             "required": bool(info["required"]), "manual": True})
    return {"filled": filled, "files": 0, "blockers": blockers}
