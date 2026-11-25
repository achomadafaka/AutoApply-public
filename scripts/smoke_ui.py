"""Smoke-test a running local instance using fictional data only."""
import argparse
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright


def loopback(url: str) -> str:
    if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise argparse.ArgumentTypeError("Smoke testing is restricted to loopback.")
    return url.rstrip("/")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--ui", type=loopback, default="http://localhost:5173")
    cli.add_argument("--api", type=loopback, default="http://127.0.0.1:8000")
    args = cli.parse_args()
    title = f"Synthetic smoke job {uuid4().hex[:8]}"
    job_id = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(args.ui, wait_until="domcontentloaded")
            expect(page.get_by_role("heading", name="AutoApply Control Room")).to_be_visible()
            page.get_by_role("link", name="New Job", exact=True).click()
            expect(page.get_by_role("heading", name="New job", exact=True)).to_be_visible()
            page.get_by_label("Title", exact=True).fill(title)
            page.get_by_label("Company", exact=True).fill("Example Test Company")
            with page.expect_response(lambda r: r.url == args.api + "/v1/jobs"
                                      and r.request.method == "POST") as created:
                page.get_by_role("button", name="Create job", exact=True).click()
            assert created.value.status == 201, created.value.text()
            job_id = created.value.json()["id"]
            page.goto(f"{args.ui}/jobs/{job_id}")
            expect(page.get_by_role("heading", name=title)).to_be_visible()
            assert not errors, errors
            browser.close()
    finally:
        if job_id:
            httpx.delete(f"{args.api}/v1/jobs/{job_id}").raise_for_status()
    print("UI smoke passed: dashboard, create a synthetic job, open its detail, remove it.")


if __name__ == "__main__":
    main()
