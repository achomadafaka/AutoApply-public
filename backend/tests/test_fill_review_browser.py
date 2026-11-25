"""Chromium exercises a realistic hosted application without sending any traffic."""

import pytest

from app.automation.review_fill import FORM, allowed_target, fill_form

playwright = pytest.importorskip("playwright.sync_api")

SAMPLE_FORM = """
<form action="/submit" method="post">
  <label for="first_name">First Name*</label><input id="first_name" required>
  <label for="last_name">Last Name*</label><input id="last_name" required>
  <label for="email">Email*</label><input id="email" type="email" required>
  <label for="cv">Resume/CV*</label><input id="cv" type="file" required>
  <label for="sql">What is your primary analysis tool?*</label>
  <select id="sql" required><option value="">Choose...</option><option>SQL</option></select>
  <fieldset><legend>Preferred work arrangement*</legend>
    <label><input type="radio" name="work" value="remote" required>Remote</label>
    <label><input type="radio" name="work" value="hybrid" required>Hybrid</label>
  </fieldset>
  <button type="submit">Submit application</button>
</form>
"""
PROFILE = {
    "first_name": "Avery",
    "last_name": "Example",
    "email": "avery@example.invalid",
}
ANSWERS = {
    "What is your primary analysis tool?": "SQL",
    "Preferred work arrangement": "Hybrid",
}


@pytest.fixture()
def browser_page():
    with playwright.sync_playwright() as engine:
        browser = engine.chromium.launch(headless=True)
        page = browser.new_page()
        page.route("**/*", lambda route: route.abort())
        yield page
        browser.close()


def test_fill_real_browser_without_submitting(browser_page):
    browser_page.set_content(SAMPLE_FORM)
    browser_page.evaluate("""window.submitted = false;
      document.querySelector('form').addEventListener('submit', e => {
        e.preventDefault(); window.submitted = true;
      })""")

    form = browser_page.locator(FORM)
    result = fill_form(form, PROFILE)
    assert result["filled"] == 3
    assert result["files"] == 0
    assert form.locator("#email").input_value() == PROFILE["email"]
    assert form.locator("#cv").evaluate("input => input.files.length") == 0
    assert form.locator("#sql").input_value() == ""
    assert not form.locator("[value=hybrid]").is_checked()
    assert browser_page.evaluate("window.submitted") is False


def test_unclassified_consent_stays_manual(browser_page):
    browser_page.set_content(SAMPLE_FORM.replace("</form>", """
        <label for="retain">May we retain your application for future roles?</label>
        <select id="retain" required><option value="">Choose...</option><option>Yes</option></select>
        <label for="phone">I agree to be contacted</label><input id="phone" type="tel">
        <label><input type="checkbox" required>I accept the privacy policy</label>
        </form>"""))
    form = browser_page.locator(FORM)
    result = fill_form(form, {**PROFILE, "phone": "12345"})
    blockers = {q["name"]: q for q in result["blockers"]}
    assert blockers["retain"]["manual"]
    assert not form.locator("#retain").input_value()
    assert not form.locator("#phone").input_value()
    assert not form.locator("[type=checkbox]").is_checked()


def test_only_official_https_hosts_allowed():
    assert allowed_target("https://job-boards.greenhouse.io/acme/jobs/123")
    assert allowed_target("https://job-boards.eu.greenhouse.io/acme/jobs/123")
    assert not allowed_target("https://job-boards.greenhouse.io.evil.invalid/acme/jobs/123")
    assert not allowed_target("https://job-boards.greenhouse.io@evil.invalid/acme/jobs/123")
    assert not allowed_target("http://job-boards.greenhouse.io/acme/jobs/123")


def test_submit_capable_combobox_option_is_never_clicked(browser_page):
    browser_page.set_content(SAMPLE_FORM.replace("</form>", """
      <div class="select__container">
        <label for="country">Country*</label>
        <input id="country" role="combobox" aria-controls="options">
        <div id="options" role="listbox">
          <button role="option" onclick="window.optionClicked = true">Switzerland</button>
        </div>
      </div></form>"""))
    browser_page.evaluate("""() => {
      window.optionClicked = false;
      window.submitEvents = 0;
      document.querySelector('form').addEventListener('submit', event => {
        event.preventDefault(); window.submitEvents++;
      });
    }""")
    form = browser_page.locator(FORM)
    result = fill_form(form, PROFILE)
    assert next(q for q in result["blockers"] if q["name"] == "country")["manual"]
    assert browser_page.evaluate("window.optionClicked") is False
    assert browser_page.evaluate("window.submitEvents") == 0


@pytest.mark.parametrize("contact_only", [False, True])
def test_real_runner_requires_manual_fields_and_never_submits(browser_page, tmp_path, monkeypatch, contact_only):
    from contextlib import nullcontext
    from types import SimpleNamespace
    import sqlite3

    from app.automation import playwright_runner as runner
    from app.repo import create_application, create_job

    cv = tmp_path / "test-resume.txt"
    cv.write_text("Synthetic analytics résumé.")
    answers = tmp_path / "answers.json"
    import json
    answers.write_text(json.dumps({**ANSWERS, "Optional saved screening answer": "Saved value"}))
    monkeypatch.chdir(tmp_path)
    settings = SimpleNamespace(
        **{f"profile_{key}": PROFILE.get(key) for key in (
            "first_name", "last_name", "email", "linkedin", "github", "website", "location"
        )},
        profile_phone="+10000000000",
        profile_resume_path=str(cv), profile_base_resume_path=None, profile_cover_letter_path=None,
        profile_answers_path=str(answers), automation_interactive_timeout_sec=10,
    )
    monkeypatch.setattr(runner, "get_settings", lambda: settings)
    monkeypatch.setattr(runner, "_wait_for_interactive_session", lambda *_: "closed")

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    from pathlib import Path
    db.executescript((Path(__file__).resolve().parents[1] / "migrations/001_init.sql").read_text())
    url = "https://job-boards.greenhouse.io/example/jobs/123"
    job = create_job(db, {"source": "manual", "title": "Junior data analyst",
                          "company": "Test fixture", "url": url, "status": "new"})
    app = create_application(db, job["id"], "greenhouse", "fill_review")
    if contact_only:
        app.update(contact_only=True, confirmed_answers=ANSWERS)
    test_form = SAMPLE_FORM.replace("</form>", """
      <label for="phone">Phone</label><input id="phone" type="tel">
      <label for="optional">Optional saved screening answer</label><input id="optional">
      </form>
    """)
    synthetic_requests = []
    def serve_fixture(route):
        synthetic_requests.append(route.request.method)
        route.fulfill(status=200, body=test_form, content_type="text/html")
    browser_page.route(url, serve_fixture)
    fake_engine = SimpleNamespace(chromium=SimpleNamespace(launch=lambda **_: SimpleNamespace(
        new_page=lambda **_: browser_page, close=lambda: None,
    )))

    result = runner._run_fill_review(db, app, url, lambda: nullcontext(fake_engine))
    stored = db.execute("SELECT state, last_error FROM applications WHERE id = ?", (app["id"],)).fetchone()
    event = db.execute("SELECT event, details_json FROM application_history ORDER BY created_at DESC").fetchone()
    assert result == {"status": "review_closed", "reason": "closed"}
    assert tuple(stored) == ("awaiting_review", "Review the form and attach documents yourself.")
    assert event["event"] == "fill_review_needs_input"
    assert json.loads(event["details_json"]) == {
        "filled": 3 if contact_only else 4, "files": 0, "blockers": 3,
    }
    assert browser_page.locator("#phone").input_value() == ("" if contact_only else "+10000000000")
    assert browser_page.locator("#optional").input_value() == ""
    assert synthetic_requests == ["GET"]
    assert not browser_page.locator(FORM).evaluate("form => form.checkValidity()")


def test_submission_evidence_is_role_scoped_and_visible(browser_page):
    from app.automation.review_fill import review_evidence

    target = "https://job-boards.greenhouse.io/example/jobs/123"
    def serve(route):
        route.fulfill(status=200, body="""
          <form id="application-form">
            <fieldset id="verification" hidden>
              <legend>Enter the 8-character security code</legend>
              <input id="security-input-0">
            </fieldset>
          </form>
          <main><h1 hidden>Thank you for applying!</h1></main>
        """, content_type="text/html")
    browser_page.route("https://job-boards.greenhouse.io/**", serve)
    browser_page.goto(target)
    assert review_evidence(browser_page, target) is None
    browser_page.locator("#verification").evaluate("el => el.hidden = false")
    assert review_evidence(browser_page, target) == "verification"
    browser_page.goto(target + "/confirmation")
    assert review_evidence(browser_page, target) is None
    browser_page.locator("main h1").evaluate("el => el.hidden = false")
    browser_page.locator("form").evaluate("el => el.remove()")
    assert review_evidence(browser_page, target) == "confirmed"
    assert review_evidence(browser_page, target.replace("/123", "/456")) is None


def test_invalid_optional_control_is_a_blocker(browser_page):
    browser_page.set_content("""
      <form id="application-form">
        <label for="email">Email*</label><input id="email" type="email">
        <label for="website">Website</label><input id="website" type="url">
      </form>
    """)
    form = browser_page.locator(FORM)
    result = fill_form(form, {**PROFILE, "website": "not a URL"})
    assert [blocker["label"] for blocker in result["blockers"]] == ["Website"]


def test_fields_reset_after_input_are_not_reported_ready(browser_page):
    requests = []
    url = "https://job-boards.greenhouse.io/example/jobs/4321"
    html = SAMPLE_FORM + """<script>
    document.querySelector('#first_name').addEventListener('input', e => {
      setTimeout(() => { e.target.value = ''; }, 500);
    });
    </script>"""
    def serve(route):
        requests.append(route.request.method)
        route.fulfill(status=200, body=html, content_type="text/html")
    browser_page.route(url, serve)
    browser_page.goto(url)
    form = browser_page.locator(FORM)
    result = fill_form(form, PROFILE)
    assert any(b["name"] == "first_name" for b in result["blockers"])
    assert result["filled"] == 2
    assert result["files"] == 0
    assert requests == ["GET"]


def test_cleared_file_and_stale_upload_marker_never_count(browser_page):
    browser_page.set_content(SAMPLE_FORM.replace(
        '<input id="cv" type="file" required>',
        '<div class="attachment-upload"><input id="cv" type="file" required>'
        '<span data-upload-status="uploaded">Different-CV.pdf</span></div>',
    ))
    form = browser_page.locator(FORM)
    cv = form.locator("#cv")
    cv.set_input_files({"name": "test.txt", "mimeType": "text/plain", "buffer": b"Synthetic."})
    assert fill_form(form, PROFILE)["files"] == 0
    cv.evaluate("el => el.value = ''")
    result = fill_form(form, PROFILE)
    assert result["files"] == 0
    assert next(q for q in result["blockers"] if q["name"] == "cv")["manual"]
    assert cv.evaluate("el => el.files.length") == 0


def test_guard_blocks_submission_and_late_requests_until_manual_handoff(browser_page):
    from app.automation.playwright_runner import _START_PREFILL_GUARD

    url = "https://fixture.invalid/job"
    html = SAMPLE_FORM + """<script>
      const form = document.querySelector('form');
      window.submitEvents = 0;
      form.addEventListener('submit', event => {
        window.submitEvents++;
      });
      for (const selector of ['#sql', '[value=hybrid]', '#cv']) {
        form.querySelector(selector).removeAttribute('required');
      }
      form.querySelector('[value=remote]').removeAttribute('required');
      document.querySelector('#first_name').addEventListener('input', () => {
        form.requestSubmit();
        form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
        setTimeout(() => {
          form.submit();
          fetch('/post', {method: 'POST'}).catch(() => {});
        }, 850);
        setTimeout(() => { form.querySelector('#first_name').value = ''; }, 850);
      });
    </script>"""
    requests = []
    attempts = []
    handoff = []
    def serve(route):
        requests.append((route.request.method, route.request.url))
        route.fulfill(status=200, body=html if route.request.url == url else "Synthetic receipt.",
                      content_type="text/html")
    browser_page.route("https://fixture.invalid/**", serve)
    browser_page.goto(url)
    browser_page.expose_binding("__autoapplyNoteUserSubmit", lambda _: attempts.append(True))
    browser_page.expose_binding("__autoapplyNoteInteraction", lambda _: handoff.append(True))
    browser_page.route("https://fixture.invalid/**",
                       lambda route: route.fallback() if handoff else route.abort())
    browser_page.evaluate(_START_PREFILL_GUARD, FORM)
    assert fill_form(browser_page.locator(FORM), PROFILE)["filled"] == 3
    browser_page.evaluate("() => window.__autoapplyArmHandoff()")
    browser_page.wait_for_function("document.querySelector('#first_name').value === ''")
    from app.automation.review_fill import inspect_form
    result = inspect_form(browser_page.locator(FORM), PROFILE)
    assert result["filled"] == 2
    assert any(q["name"] == "first_name" for q in result["blockers"])
    assert requests == [("GET", url)]
    assert browser_page.evaluate("window.submitEvents") == 0
    assert not attempts
    browser_page.locator("#first_name").evaluate("el => el.value = 'Avery'")
    browser_page.get_by_role("button", name="Submit application").click()
    browser_page.wait_for_url("**/submit")
    assert requests[-1] == ("POST", "https://fixture.invalid/submit")
    assert attempts == [True]
